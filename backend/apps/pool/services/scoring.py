"""
Motor de puntuación de la bolilla.

Contiene toda la lógica de negocio para calcular y registrar los
puntos que obtiene cada participante según los resultados del torneo.

Reglas de puntuación:
    Fase de grupos:
        +3 por victoria
        +1 por empate
        +6 por clasificar (top 2 o mejor tercero)
        +2 por quedar primero de grupo
    Fases eliminatorias:
        +10 por clasificar a octavos
        +15 por clasificar a cuartos
        +20 por clasificar a semifinales
        +25 por clasificar a la final
        +25 por ganar el Mundial
    Premios individuales (al finalizar el torneo):
        +20 por acertar el MVP
        +10 por acertar el Pichichi
        +5  por acertar el Zamora
"""

import logging

from apps.tournament.models import Match, NationalTeam

from ..models import Participant, ScoreLog

logger = logging.getLogger(__name__)

# ── Constantes de puntuación ──────────────────────────────────────────────────

POINTS_WIN = 3
POINTS_DRAW = 1
POINTS_QUALIFY_GROUP = 6
POINTS_FIRST_IN_GROUP = 2
POINTS_ROUND_OF_16 = 10
POINTS_QUARTER_FINAL = 15
POINTS_SEMI_FINAL = 20
POINTS_FINAL = 25
POINTS_CHAMPION = 25
POINTS_MVP = 20
POINTS_TOP_SCORER = 10
POINTS_BEST_GOALKEEPER = 5

# Número de partidos por grupo (4 equipos, todos contra todos → C(4,2) = 6)
MATCHES_PER_GROUP = 6


def process_match_result(match: Match) -> list[ScoreLog]:
    """
    Procesa el resultado de un partido y genera los ScoreLogs correspondientes.

    Debe llamarse cuando un partido se marca como finalizado.
    Evita generar duplicados si se llama varias veces sobre el mismo partido.

    Args:
        match: Instancia de Match con is_finished=True y scores definidos.

    Returns:
        Lista de ScoreLog creados en esta llamada (vacía si ya estaban creados).
    """
    if not match.is_finished:
        logger.warning(
            "Se intentó procesar el partido %s que no está finalizado.", match
        )
        return []

    # Idempotencia: eliminar logs previos de este partido antes de recalcular
    deleted_count, _ = ScoreLog.objects.filter(match=match).delete()
    if deleted_count:
        logger.info(
            "Eliminados %d ScoreLog previos del partido %s (recalculando).",
            deleted_count,
            match,
        )

    created_logs: list[ScoreLog] = []

    teams_in_match = [match.home_team, match.away_team]

    for team in teams_in_match:
        participants_with_team = Participant.objects.filter(teams=team)

        for participant in participants_with_team:
            points = _calculate_match_points(match, team)
            if points == 0:
                continue

            reason = _build_match_reason(match, team, points)
            log = ScoreLog.objects.create(
                participant=participant,
                team=team,
                match=match,
                points_earned=points,
                reason=reason,
            )
            created_logs.append(log)
            logger.debug("ScoreLog creado: %s", log)

    return created_logs


def process_group_completion(group: str) -> list[ScoreLog]:
    """
    Otorga puntos de clasificación cuando todos los partidos de un grupo terminan.

    - ADVANCE_GRP (+6): 1º y 2º clasificado del grupo.
    - TOP_GROUP   (+2): solo al 1º del grupo.

    Los 8 mejores terceros (que también avanzan) se calculan aparte, cuando
    los 12 grupos estén completos, mediante `process_best_third_places()`.

    Idempotente: borra y recrea los logs con las razones de este grupo antes
    de recalcular, por lo que es seguro llamarlo al corregir un resultado.

    Args:
        group: Letra del grupo (A-L).

    Returns:
        Lista de ScoreLog creados, o lista vacía si el grupo no está completo.
    """
    group_matches = Match.objects.filter(
        phase=Match.Phase.GROUP, group=group
    ).select_related("home_team", "away_team")

    total = group_matches.count()
    finished = group_matches.filter(is_finished=True).count()
    if total < MATCHES_PER_GROUP or finished < total:
        logger.debug(
            "Grupo %s: %d/%d partidos terminados. Esperando.", group, finished, total
        )
        return []

    # ── Calcular la tabla del grupo ───────────────────────────────────────
    teams_stats: dict[NationalTeam, dict[str, int]] = {}
    for match in group_matches:
        for team in (match.home_team, match.away_team):
            if team and team not in teams_stats:
                teams_stats[team] = {"pts": 0, "gf": 0, "ga": 0}

    for match in group_matches:
        if match.home_score is None or match.away_score is None:
            continue
        home, away = match.home_team, match.away_team
        if home is None or away is None:
            continue
        hs, as_ = match.home_score, match.away_score
        if hs > as_:
            teams_stats[home]["pts"] += 3
        elif hs == as_:
            teams_stats[home]["pts"] += 1
            teams_stats[away]["pts"] += 1
        else:
            teams_stats[away]["pts"] += 3
        teams_stats[home]["gf"] += hs
        teams_stats[home]["ga"] += as_
        teams_stats[away]["gf"] += as_
        teams_stats[away]["ga"] += hs

    # Orden: puntos ↓, diferencia de goles ↓, goles a favor ↓
    standings = sorted(
        teams_stats.items(),
        key=lambda x: (x[1]["pts"], x[1]["gf"] - x[1]["ga"], x[1]["gf"]),
        reverse=True,
    )

    # ── Idempotencia: borrar logs previos de clasificación de este grupo ──
    advance_reason = f"Clasificado desde grupo {group}"
    top_reason = f"1\u00ba de grupo {group}"
    del1, _ = ScoreLog.objects.filter(reason=advance_reason).delete()
    del2, _ = ScoreLog.objects.filter(reason=top_reason).delete()
    deleted = del1 + del2
    if deleted:
        logger.info(
            "Grupo %s: %d logs de clasificación previos eliminados.", group, deleted
        )

    # ── Crear los nuevos logs ─────────────────────────────────────────────
    created: list[ScoreLog] = []
    for rank, (team, stats) in enumerate(standings):
        if rank >= 2:
            break  # Solo top 2 reciben ADVANCE_GRP automáticamente

        logger.info(
            "Grupo %s: %s → %dº (pts=%d gd=%+d gf=%d)",
            group,
            team,
            rank + 1,
            stats["pts"],
            stats["gf"] - stats["ga"],
            stats["gf"],
        )
        created.extend(_award_team_points(team, POINTS_QUALIFY_GROUP, advance_reason))
        if rank == 0:
            created.extend(_award_team_points(team, POINTS_FIRST_IN_GROUP, top_reason))

    return created


def award_phase_advancement(team: NationalTeam, phase: Match.Phase) -> list[ScoreLog]:
    """
    Otorga puntos por avanzar a una fase eliminatoria.

    Args:
        team: Selección que avanza de fase.
        phase: Fase a la que avanza (R16, QF, SF, FIN).

    Returns:
        Lista de ScoreLog creados.
    """
    points_map = {
        Match.Phase.ROUND_OF_16: POINTS_ROUND_OF_16,
        Match.Phase.QUARTER_FINAL: POINTS_QUARTER_FINAL,
        Match.Phase.SEMI_FINAL: POINTS_SEMI_FINAL,
        Match.Phase.FINAL: POINTS_FINAL,
    }
    points = points_map.get(phase, 0)
    if points == 0:
        return []

    reason = f"Clasificado a {Match.Phase(phase).label}"
    return _award_team_points(team, points, reason)


def award_champion(team: NationalTeam) -> list[ScoreLog]:
    """Otorga los puntos por ganar el Mundial."""
    return _award_team_points(team, POINTS_CHAMPION, "¡Campeón del Mundial!")


def award_individual_prizes(
    real_mvp: str,
    real_top_scorer: str,
    real_best_goalkeeper: str,
) -> list[ScoreLog]:
    """
    Otorga puntos por acertar los premios individuales al final del torneo.

    Args:
        real_mvp: Nombre real del MVP del torneo.
        real_top_scorer: Nombre real del Pichichi.
        real_best_goalkeeper: Nombre real del Zamora.

    Returns:
        Lista de ScoreLog creados.
    """
    created: list[ScoreLog] = []

    prize_config = [
        ("predicted_mvp", real_mvp, POINTS_MVP, "Acertó el MVP del torneo"),
        (
            "predicted_top_scorer",
            real_top_scorer,
            POINTS_TOP_SCORER,
            "Acertó el Pichichi",
        ),
        (
            "predicted_best_goalkeeper",
            real_best_goalkeeper,
            POINTS_BEST_GOALKEEPER,
            "Acertó el Zamora",
        ),
    ]

    for field, real_value, points, reason in prize_config:
        if not real_value:
            continue
        correct_participants = Participant.objects.filter(**{field: real_value})
        for participant in correct_participants:
            # Usamos el primer equipo del participante como referencia (premios no son de equipo)
            team = participant.teams.first()
            if team is None:
                continue
            log = ScoreLog.objects.create(
                participant=participant,
                team=team,
                match=None,
                points_earned=points,
                reason=reason,
            )
            created.append(log)

    return created


# ── Funciones auxiliares (privadas) ───────────────────────────────────────────


def _calculate_match_points(match: Match, team: NationalTeam) -> int:
    """Calcula los puntos que obtiene un equipo por un partido concreto."""
    if match.home_score is None or match.away_score is None:
        return 0

    is_home = match.home_team == team
    my_score = match.home_score if is_home else match.away_score
    rival_score = match.away_score if is_home else match.home_score

    if my_score > rival_score:
        return POINTS_WIN
    if my_score == rival_score:
        return POINTS_DRAW
    return 0


def _build_match_reason(match: Match, team: NationalTeam, points: int) -> str:
    """Construye el texto descriptivo del motivo de la puntuación."""
    rival = match.away_team if match.home_team == team else match.home_team
    if points == POINTS_WIN:
        return f"Victoria vs {rival.name}"
    if points == POINTS_DRAW:
        return f"Empate vs {rival.name}"
    return f"Derrota vs {rival.name}"


def _award_team_points(
    team: NationalTeam,
    points: int,
    reason: str,
) -> list[ScoreLog]:
    """Crea ScoreLogs para todos los participantes que tienen un equipo dado."""
    created: list[ScoreLog] = []
    participants = Participant.objects.filter(teams=team)
    for participant in participants:
        log = ScoreLog.objects.create(
            participant=participant,
            team=team,
            match=None,
            points_earned=points,
            reason=reason,
        )
        created.append(log)
    return created

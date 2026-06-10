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
        +3 por victoria solo si se resuelve en 90'
        +1 si se resuelve en prórroga o penaltis (se considera empate)
        +10 por clasificar a octavos
        +15 por clasificar a cuartos
        +20 por clasificar a semifinales
        +25 por clasificar a la final
        +10 por quedar tercero
        +25 por ganar el Mundial
    Premios individuales (al finalizar el torneo):
        +20 por acertar el MVP
        +10 por acertar el Pichichi
        +5  por acertar el Zamora
"""

import logging

from apps.tournament.models import Match, NationalTeam

from ..models import (
    REASON_ADVANCE_PHASE,
    REASON_CHAMPION,
    REASON_GROUP_ADVANCE,
    REASON_GROUP_FIRST,
    REASON_MATCH_DRAW,
    REASON_MATCH_LOSS,
    REASON_MATCH_WIN,
    REASON_THIRD_PLACE,
    Participant,
    ScoreLog,
    render_scorelog_reason,
)

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
POINTS_THIRD_PLACE = 10
POINTS_CHAMPION = 30
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

            reason_code, reason_context, reason = _build_match_reason_payload(
                match, team, points
            )
            log = ScoreLog.objects.create(
                participant=participant,
                team=team,
                match=match,
                points_earned=points,
                reason_code=reason_code,
                reason_context=reason_context,
                reason=reason,
            )
            created_logs.append(log)
            logger.debug("ScoreLog creado: %s", log)

    created_logs.extend(_award_post_match_bonuses(match))

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
    _delete_group_classification_logs(group)

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
        created.extend(
            _award_team_points(
                team,
                POINTS_QUALIFY_GROUP,
                REASON_GROUP_ADVANCE,
                {"group": group},
                fallback_reason=advance_reason,
            )
        )
        if rank == 0:
            created.extend(
                _award_team_points(
                    team,
                    POINTS_FIRST_IN_GROUP,
                    REASON_GROUP_FIRST,
                    {"group": group},
                    fallback_reason=top_reason,
                )
            )

    return created


def process_group_completion_from_standings(
    group: str,
    ranked_teams: list[NationalTeam],
) -> list[ScoreLog]:
    """
    Otorga puntos de clasificación usando standings oficiales de API.

    Args:
        group: Letra del grupo (A-L).
        ranked_teams: Equipos ordenados por clasificación (1º, 2º, ...).

    Returns:
        Lista de ScoreLog creados.
    """
    if len(ranked_teams) < 2:
        logger.warning(
            "Grupo %s: standings insuficientes desde API (%d equipos).",
            group,
            len(ranked_teams),
        )
        return []

    _delete_group_classification_logs(group)

    advance_reason = f"Clasificado desde grupo {group}"
    top_reason = f"1\u00ba de grupo {group}"

    first_team = ranked_teams[0]
    second_team = ranked_teams[1]

    created: list[ScoreLog] = []
    created.extend(
        _award_team_points(
            first_team,
            POINTS_QUALIFY_GROUP,
            REASON_GROUP_ADVANCE,
            {"group": group},
            fallback_reason=advance_reason,
        )
    )
    created.extend(
        _award_team_points(
            second_team,
            POINTS_QUALIFY_GROUP,
            REASON_GROUP_ADVANCE,
            {"group": group},
            fallback_reason=advance_reason,
        )
    )
    created.extend(
        _award_team_points(
            first_team,
            POINTS_FIRST_IN_GROUP,
            REASON_GROUP_FIRST,
            {"group": group},
            fallback_reason=top_reason,
        )
    )

    logger.info(
        "Grupo %s: standings API aplicados (1º=%s, 2º=%s).",
        group,
        first_team.code,
        second_team.code,
    )
    return created


def award_phase_advancement(
    team: NationalTeam,
    phase: Match.Phase,
    match: Match | None = None,
) -> list[ScoreLog]:
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

    reason_context = {"phase": phase.value}
    reason = render_scorelog_reason(REASON_ADVANCE_PHASE, reason_context)
    return _award_team_points(
        team,
        points,
        REASON_ADVANCE_PHASE,
        reason_context,
        match=match,
        fallback_reason=reason,
    )


def award_third_place(
    team: NationalTeam,
    match: Match | None = None,
) -> list[ScoreLog]:
    """Otorga los puntos por quedar 3º."""
    return _award_team_points(
        team,
        POINTS_THIRD_PLACE,
        REASON_THIRD_PLACE,
        {},
        match=match,
        fallback_reason=render_scorelog_reason(REASON_THIRD_PLACE),
    )


def award_champion(
    team: NationalTeam,
    match: Match | None = None,
) -> list[ScoreLog]:
    """Otorga los puntos por ganar el Mundial."""
    return _award_team_points(
        team,
        POINTS_CHAMPION,
        REASON_CHAMPION,
        {},
        match=match,
        fallback_reason=render_scorelog_reason(REASON_CHAMPION),
    )


# ── Funciones auxiliares (privadas) ───────────────────────────────────────────


def _calculate_match_points(match: Match, team: NationalTeam) -> int:
    """Calcula los puntos que obtiene un equipo por un partido concreto."""
    if match.home_score is None or match.away_score is None:
        return 0

    is_home = match.home_team == team
    my_score = match.home_score if is_home else match.away_score
    rival_score = match.away_score if is_home else match.home_score

    if match.phase != Match.Phase.GROUP and not match.decided_in_90:
        return POINTS_DRAW

    if my_score > rival_score:
        return POINTS_WIN
    if my_score == rival_score:
        return POINTS_DRAW
    return 0


def _build_match_reason_payload(
    match: Match, team: NationalTeam, points: int
) -> tuple[str, dict[str, str], str]:
    """Construye código, contexto y texto descriptivo del motivo de la puntuación."""
    rival = match.away_team if match.home_team == team else match.home_team
    reason_context = {"rival": rival.name if rival else ""}
    if points == POINTS_WIN:
        return (
            REASON_MATCH_WIN,
            reason_context,
            render_scorelog_reason(
                REASON_MATCH_WIN,
                reason_context,
                f"Victoria vs {reason_context['rival']}",
            ),
        )
    if points == POINTS_DRAW:
        return (
            REASON_MATCH_DRAW,
            reason_context,
            render_scorelog_reason(
                REASON_MATCH_DRAW,
                reason_context,
                f"Empate vs {reason_context['rival']}",
            ),
        )
    return (
        REASON_MATCH_LOSS,
        reason_context,
        render_scorelog_reason(
            REASON_MATCH_LOSS,
            reason_context,
            f"Derrota vs {reason_context['rival']}",
        ),
    )


def _award_team_points(
    team: NationalTeam,
    points: int,
    reason_code: str,
    reason_context: dict[str, str] | None = None,
    match: Match | None = None,
    fallback_reason: str = "",
) -> list[ScoreLog]:
    """Crea ScoreLogs para todos los participantes que tienen un equipo dado."""
    created: list[ScoreLog] = []
    reason_context = reason_context or {}
    reason = render_scorelog_reason(reason_code, reason_context, fallback_reason)
    ScoreLog.objects.filter(team=team, match=match, reason_code=reason_code).delete()
    participants = Participant.objects.filter(teams=team)
    for participant in participants:
        log = ScoreLog.objects.create(
            participant=participant,
            team=team,
            match=match,
            points_earned=points,
            reason_code=reason_code,
            reason_context=reason_context,
            reason=reason,
        )
        created.append(log)
    return created


def _award_post_match_bonuses(match: Match) -> list[ScoreLog]:
    """Otorga los puntos de avance o campeón asociados al partido cerrado."""
    if match.phase == Match.Phase.GROUP:
        return []

    winner = match.knockout_winner
    if winner is None:
        return []

    if match.phase == Match.Phase.FINAL:
        return award_champion(winner, match=match)

    if match.phase == Match.Phase.THIRD_PLACE:
        return award_third_place(winner, match=match)

    next_phase_map = {
        Match.Phase.ROUND_OF_32: Match.Phase.ROUND_OF_16,
        Match.Phase.ROUND_OF_16: Match.Phase.QUARTER_FINAL,
        Match.Phase.QUARTER_FINAL: Match.Phase.SEMI_FINAL,
        Match.Phase.SEMI_FINAL: Match.Phase.FINAL,
    }
    next_phase = next_phase_map.get(match.phase)
    if next_phase is None:
        return []

    return award_phase_advancement(winner, next_phase, match=match)


def _delete_group_classification_logs(group: str) -> None:
    """Elimina logs de clasificación de un grupo concreto para recalcular idempotente."""
    del1, _ = ScoreLog.objects.filter(
        reason_code=REASON_GROUP_ADVANCE,
        reason_context__group=group,
    ).delete()
    del2, _ = ScoreLog.objects.filter(
        reason_code=REASON_GROUP_FIRST,
        reason_context__group=group,
    ).delete()
    deleted = del1 + del2
    if deleted:
        logger.info(
            "Grupo %s: %d logs de clasificación previos eliminados.", group, deleted
        )

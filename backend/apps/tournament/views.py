"""Vistas de la app tournament."""

from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from apps.pool.models import (
    REASON_BEST_GOALKEEPER,
    REASON_MVP,
    REASON_TOP_SCORER,
    render_scorelog_reason,
)
from apps.pool.services.scoring import (
    POINTS_BEST_GOALKEEPER,
    POINTS_MVP,
    POINTS_TOP_SCORER,
    process_match_result,
)

from .models import Match, NationalTeam, TournamentConfig


def results(request: HttpRequest) -> HttpResponse:
    """Página con todos los resultados del mundial agrupados por fase."""
    phases = [
        (Match.Phase.GROUP, _("Fase de grupos")),
        (Match.Phase.ROUND_OF_32, _("Dieciseisavos de final")),
        (Match.Phase.ROUND_OF_16, _("Octavos de final")),
        (Match.Phase.QUARTER_FINAL, _("Cuartos de final")),
        (Match.Phase.SEMI_FINAL, _("Semifinales")),
        (Match.Phase.THIRD_PLACE, _("3er y 4º puesto")),
        (Match.Phase.FINAL, _("Final")),
    ]
    matches_by_phase = [
        {
            "phase": phase.value,
            "label": label,
            "is_group": phase == Match.Phase.GROUP,
            "matches": Match.objects.filter(phase=phase)  # pyright: ignore[reportAttributeAccessIssue]
            .select_related("home_team", "away_team")
            .order_by("scheduled_at"),
        }
        for phase, label in phases
        if Match.objects.filter(phase=phase).exists()  # pyright: ignore[reportAttributeAccessIssue]
    ]
    return render(
        request, "tournament/results.html", {"matches_by_phase": matches_by_phase}
    )


@login_required
@require_POST
def admin_set_result(request: HttpRequest, match_id: int) -> HttpResponse:
    """Actualiza el resultado de un partido. Solo para staff."""
    if not request.user.is_staff:
        return redirect("pool:dashboard")

    match = get_object_or_404(Match, id=match_id)
    home_score = request.POST.get("home_score", "").strip()
    away_score = request.POST.get("away_score", "").strip()
    penalties_winner = request.POST.get("penalties_winner", "").strip()
    decided_in_90 = request.POST.get("decided_in_90", "1") == "1"
    is_finished = request.POST.get("is_finished") == "1"

    if home_score.isdigit() and away_score.isdigit():
        match.home_score = int(home_score)
        match.away_score = int(away_score)
        match.is_finished = is_finished
        match.decided_in_90 = (
            decided_in_90 if match.phase != Match.Phase.GROUP else True
        )
        is_knockout = match.phase != Match.Phase.GROUP
        is_draw = match.home_score == match.away_score
        if (
            is_finished
            and is_knockout
            and is_draw
            and not match.decided_in_90
            and penalties_winner
            in (Match.PenaltiesWinner.HOME, Match.PenaltiesWinner.AWAY)
        ):
            match.penalties_winner = penalties_winner
        else:
            match.penalties_winner = ""
        match.save()
        if is_finished:
            process_match_result(match)

    fecha_retorno = request.POST.get("fecha_retorno", "")
    if fecha_retorno:
        from django.urls import reverse

        return redirect(
            f"{reverse('tournament:gestion')}?fecha={fecha_retorno}#corregir"
        )
    return redirect("tournament:gestion")


@login_required
@require_POST
def admin_recalculate(request: HttpRequest) -> HttpResponse:
    """Recalcula las puntuaciones de todos los partidos finalizados. Solo para staff."""
    if not request.user.is_staff:
        return redirect("pool:dashboard")

    for match in Match.objects.filter(is_finished=True):  # pyright: ignore[reportAttributeAccessIssue]
        process_match_result(match)

    return redirect("tournament:gestion")


@login_required
@require_POST
def admin_award_prizes(request: HttpRequest) -> HttpResponse:
    """
    Adjudica los premios individuales (MVP, Pichichi, Zamora). Solo para staff.

    El admin introduce el nombre real del ganador (para referencia) y marca
    manualmente qué participantes acertaron, lo que permite gestionar faltas
    de ortografía o variaciones en la escritura.

    Es idempotente: borra los ScoreLogs previos de cada premio antes de recrearlos.
    """
    if not request.user.is_staff:
        return redirect("pool:dashboard")

    from apps.pool.models import Participant, ScoreLog

    config = TournamentConfig.get()

    # Guardar los nombres reales en TournamentConfig
    config.real_mvp = request.POST.get("real_mvp", "").strip()
    config.real_top_scorer = request.POST.get("real_top_scorer", "").strip()
    config.real_best_goalkeeper = request.POST.get("real_best_goalkeeper", "").strip()
    config.save()

    prize_config = [
        ("mvp", REASON_MVP, POINTS_MVP),
        ("top_scorer", REASON_TOP_SCORER, POINTS_TOP_SCORER),
        ("best_goalkeeper", REASON_BEST_GOALKEEPER, POINTS_BEST_GOALKEEPER),
    ]

    for key, reason_code, points in prize_config:
        # Idempotencia: eliminar logs previos de este premio
        ScoreLog.objects.filter(match=None, reason_code=reason_code).delete()  # pyright: ignore[reportAttributeAccessIssue]

        checked_ids = request.POST.getlist(f"winner_{key}")
        for participant in Participant.objects.filter(id__in=checked_ids):  # pyright: ignore[reportAttributeAccessIssue]
            team = participant.teams.first()
            if team is None:
                continue
            reason_context = {}
            ScoreLog.objects.create(  # pyright: ignore[reportAttributeAccessIssue]
                participant=participant,
                team=team,
                match=None,
                points_earned=points,
                reason_code=reason_code,
                reason_context=reason_context,
                reason=render_scorelog_reason(reason_code, reason_context),
            )

    return redirect("tournament:gestion")


@login_required
def gestion(request: HttpRequest) -> HttpResponse:
    """Panel de gestión del torneo. Solo para staff."""
    if not request.user.is_staff:
        return redirect("pool:dashboard")

    import datetime

    from django.utils import timezone

    from apps.pool.models import Participant, ScoreLog

    pending_matches = (
        Match.objects.filter(is_finished=False, scheduled_at__lte=timezone.now())
        .select_related("home_team", "away_team")
        .order_by("scheduled_at")
    )

    fecha_str = request.GET.get("fecha", str(timezone.now().date()))
    try:
        finished_matches_date = datetime.date.fromisoformat(fecha_str)
    except ValueError:
        finished_matches_date = timezone.now().date()

    finished_matches = (
        Match.objects.filter(is_finished=True, scheduled_at__date=finished_matches_date)
        .select_related("home_team", "away_team")
        .order_by("scheduled_at")
    )

    tournament_config = TournamentConfig.get()

    prize_participants = []
    for p in Participant.objects.filter(user__is_staff=False).select_related("user"):  # pyright: ignore[reportAttributeAccessIssue]
        prize_participants.append(
            {
                "participant": p,
                "mvp_correct": ScoreLog.objects.filter(  # pyright: ignore[reportAttributeAccessIssue]
                    participant=p, match=None, reason_code=REASON_MVP
                ).exists(),
                "top_scorer_correct": ScoreLog.objects.filter(  # pyright: ignore[reportAttributeAccessIssue]
                    participant=p, match=None, reason_code=REASON_TOP_SCORER
                ).exists(),
                "goalkeeper_correct": ScoreLog.objects.filter(  # pyright: ignore[reportAttributeAccessIssue]
                    participant=p, match=None, reason_code=REASON_BEST_GOALKEEPER
                ).exists(),
            }
        )

    r32_matches = (
        Match.objects.filter(phase=Match.Phase.ROUND_OF_32)  # pyright: ignore[reportAttributeAccessIssue]
        .select_related("home_team", "away_team", "next_match")
        .order_by("scheduled_at")
    )

    from apps.tournament.models import NationalTeam

    all_teams = NationalTeam.objects.order_by("group", "name")

    return render(
        request,
        "management/gestion.html",
        {
            "pending_matches": pending_matches,
            "finished_matches": finished_matches,
            "finished_matches_date": finished_matches_date,
            "tournament_config": tournament_config,
            "prize_participants": prize_participants,
            "r32_matches": r32_matches,
            "all_teams": all_teams,
        },
    )


@login_required
@require_POST
def gestion_set_r32_teams(request: HttpRequest, match_id: int) -> HttpResponse:
    """Asigna equipos a un partido de dieciseisavos (R32). Solo para staff."""
    if not request.user.is_staff:
        return redirect("pool:dashboard")

    match = get_object_or_404(Match, id=match_id, phase=Match.Phase.ROUND_OF_32)

    from apps.tournament.models import NationalTeam

    home_id = request.POST.get("home_team_id", "").strip()
    away_id = request.POST.get("away_team_id", "").strip()

    if home_id.isdigit():
        match.home_team = NationalTeam.objects.filter(id=int(home_id)).first()
    if away_id.isdigit():
        match.away_team = NationalTeam.objects.filter(id=int(away_id)).first()

    match.save(update_fields=["home_team", "away_team"])
    return redirect("tournament:gestion")


@login_required
@require_POST
def gestion_configure_bracket(request: HttpRequest) -> HttpResponse:
    """Configura next_match / next_match_slot para el bracket completo. Solo staff."""
    if not request.user.is_staff:
        return redirect("pool:dashboard")

    try:
        call_command("setup_bracket", verbosity=0)
        messages.success(request, "✓ Bracket configurado correctamente.")
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"Error al configurar el bracket: {exc}")

    return redirect("tournament:gestion")


def grupos(request: HttpRequest) -> HttpResponse:
    """Clasificaciones de la fase de grupos."""
    group_letters = sorted(
        NationalTeam.objects.order_by("group")
        .values_list("group", flat=True)
        .distinct()  # pyright: ignore[reportAttributeAccessIssue]
    )
    groups_data = []
    for letter in group_letters:
        group_teams = list(NationalTeam.objects.filter(group=letter))  # pyright: ignore[reportAttributeAccessIssue]
        matches = list(
            Match.objects.filter(phase=Match.Phase.GROUP, group=letter)  # pyright: ignore[reportAttributeAccessIssue]
            .select_related("home_team", "away_team")
            .order_by("scheduled_at")
        )
        standings: dict[int, dict] = {
            t.id: {
                "team": t,
                "pj": 0,
                "g": 0,
                "e": 0,
                "p": 0,
                "gf": 0,
                "gc": 0,
                "pts": 0,
            }
            for t in group_teams
        }
        for match in matches:
            if not match.is_finished:
                continue
            h, a = match.home_team_id, match.away_team_id
            if h not in standings or a not in standings:
                continue
            hs, as_ = match.home_score or 0, match.away_score or 0
            standings[h]["pj"] += 1
            standings[a]["pj"] += 1
            standings[h]["gf"] += hs
            standings[h]["gc"] += as_
            standings[a]["gf"] += as_
            standings[a]["gc"] += hs
            if hs > as_:
                standings[h]["g"] += 1
                standings[h]["pts"] += 3
                standings[a]["p"] += 1
            elif as_ > hs:
                standings[a]["g"] += 1
                standings[a]["pts"] += 3
                standings[h]["p"] += 1
            else:
                standings[h]["e"] += 1
                standings[h]["pts"] += 1
                standings[a]["e"] += 1
                standings[a]["pts"] += 1
        sorted_s = sorted(
            standings.values(),
            key=lambda x: (-x["pts"], -(x["gf"] - x["gc"]), -x["gf"]),
        )
        for i, s in enumerate(sorted_s):
            s["dg"] = s["gf"] - s["gc"]
            s["pos"] = i + 1
        groups_data.append({"letter": letter, "standings": sorted_s})
    return render(request, "tournament/grupos.html", {"groups_data": groups_data})


def eliminatorias(request: HttpRequest) -> HttpResponse:
    """Bracket del torneo en árbol horizontal."""
    final = (
        Match.objects.filter(phase=Match.Phase.FINAL)  # pyright: ignore[reportAttributeAccessIssue]
        .select_related("home_team", "away_team")
        .first()
    )
    third = (
        Match.objects.filter(phase=Match.Phase.THIRD_PLACE)  # pyright: ignore[reportAttributeAccessIssue]
        .select_related("home_team", "away_team")
        .first()
    )
    all_ko = list(
        Match.objects.filter(  # pyright: ignore[reportAttributeAccessIssue]
            phase__in=[
                Match.Phase.ROUND_OF_32,
                Match.Phase.ROUND_OF_16,
                Match.Phase.QUARTER_FINAL,
                Match.Phase.SEMI_FINAL,
            ]
        ).select_related("home_team", "away_team")
    )
    bracket_ready = any(m.next_match_id for m in all_ko)

    # Índice: next_match_id → feeders ordenados ('home' primero, h > a)
    feeders: dict[int, list] = defaultdict(list)
    for m in all_ko:
        if m.next_match_id:
            feeders[m.next_match_id].append(m)
    for k in feeders:
        feeders[k].sort(key=lambda x: x.next_match_slot, reverse=True)

    sf_matches = sorted(
        [m for m in all_ko if m.phase == Match.Phase.SEMI_FINAL],
        key=lambda x: x.next_match_slot,
        reverse=True,
    )
    qf_ordered: list = []
    r16_ordered: list = []
    r32_ordered: list = []
    for sf in sf_matches:
        for qf in feeders.get(sf.id, []):
            for r16 in feeders.get(qf.id, []):
                r32_ordered.extend(feeders.get(r16.id, []))
                r16_ordered.append(r16)
            qf_ordered.append(qf)

    if not qf_ordered:
        # Bracket no configurado: mostrar en orden de fecha
        phase_map: dict = defaultdict(list)
        for m in all_ko:
            phase_map[m.phase].append(m)
        for k in phase_map:
            phase_map[k].sort(key=lambda x: x.scheduled_at)
        r32_ordered = phase_map[Match.Phase.ROUND_OF_32]
        r16_ordered = phase_map[Match.Phase.ROUND_OF_16]
        qf_ordered = phase_map[Match.Phase.QUARTER_FINAL]
        sf_matches = phase_map[Match.Phase.SEMI_FINAL]

    return render(
        request,
        "tournament/eliminatorias.html",
        {
            "r32": r32_ordered,
            "r16": r16_ordered,
            "qf": qf_ordered,
            "sf": sf_matches,
            "final": final,
            "third": third,
            "bracket_ready": bracket_ready,
        },
    )

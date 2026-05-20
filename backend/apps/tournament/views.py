"""Vistas de la app tournament (stub inicial)."""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from apps.pool.services.scoring import (
    POINTS_BEST_GOALKEEPER,
    POINTS_MVP,
    POINTS_TOP_SCORER,
    process_match_result,
)

from .models import Match, TournamentConfig


def results(request: HttpRequest) -> HttpResponse:
    """Página con todos los resultados del mundial agrupados por fase."""
    phases: list[tuple[Match.Phase, str]] = [
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
    is_finished = request.POST.get("is_finished") == "1"

    if home_score.isdigit() and away_score.isdigit():
        match.home_score = int(home_score)
        match.away_score = int(away_score)
        match.is_finished = is_finished
        match.save()
        if is_finished:
            process_match_result(match)

    fecha_retorno = request.POST.get("fecha_retorno", "")
    if fecha_retorno:
        from django.urls import reverse

        return redirect(f"{reverse('pool:dashboard')}?fecha={fecha_retorno}#corregir")
    return redirect("pool:dashboard")


@login_required
@require_POST
def admin_recalculate(request: HttpRequest) -> HttpResponse:
    """Recalcula las puntuaciones de todos los partidos finalizados. Solo para staff."""
    if not request.user.is_staff:
        return redirect("pool:dashboard")

    for match in Match.objects.filter(is_finished=True):  # pyright: ignore[reportAttributeAccessIssue]
        process_match_result(match)

    return redirect("pool:dashboard")


# Razones fijas de ScoreLogs de premios individuales (para identificarlos en idempotencia)
_REASON_MVP = "Acertó el MVP del torneo"
_REASON_TOP_SCORER = "Acertó el Pichichi"
_REASON_GOALKEEPER = "Acertó el Zamora"


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
        ("mvp", _REASON_MVP, POINTS_MVP),
        ("top_scorer", _REASON_TOP_SCORER, POINTS_TOP_SCORER),
        ("best_goalkeeper", _REASON_GOALKEEPER, POINTS_BEST_GOALKEEPER),
    ]

    for key, reason, points in prize_config:
        # Idempotencia: eliminar logs previos de este premio
        ScoreLog.objects.filter(match=None, reason=reason).delete()  # pyright: ignore[reportAttributeAccessIssue]

        checked_ids = request.POST.getlist(f"winner_{key}")
        for participant in Participant.objects.filter(id__in=checked_ids):  # pyright: ignore[reportAttributeAccessIssue]
            team = participant.teams.first()
            if team is None:
                continue
            ScoreLog.objects.create(  # pyright: ignore[reportAttributeAccessIssue]
                participant=participant,
                team=team,
                match=None,
                points_earned=points,
                reason=reason,
            )

    return redirect("pool:dashboard")

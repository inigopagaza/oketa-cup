"""Vistas de la app tournament (stub inicial)."""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from apps.pool.services.scoring import process_match_result

from .models import Match


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

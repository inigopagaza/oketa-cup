"""Vistas de la app tournament (stub inicial)."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

from .models import Match


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
            "matches": Match.objects.filter(phase=phase)
            .select_related("home_team", "away_team")
            .order_by("scheduled_at"),
        }
        for phase, label in phases
        if Match.objects.filter(phase=phase).exists()
    ]
    return render(
        request, "tournament/results.html", {"matches_by_phase": matches_by_phase}
    )

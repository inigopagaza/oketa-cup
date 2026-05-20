"""Vistas de la app tournament (stub inicial)."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .models import Match


def results(request: HttpRequest) -> HttpResponse:
    """Página con todos los resultados del mundial agrupados por fase."""
    phases = [
        (Match.Phase.GROUP, "Fase de grupos"),
        (Match.Phase.ROUND_OF_32, "Dieciseisavos de final"),
        (Match.Phase.ROUND_OF_16, "Octavos de final"),
        (Match.Phase.QUARTER_FINAL, "Cuartos de final"),
        (Match.Phase.SEMI_FINAL, "Semifinales"),
        (Match.Phase.THIRD_PLACE, "3er y 4º puesto"),
        (Match.Phase.FINAL, "Final"),
    ]
    matches_by_phase = [
        {
            "label": label,
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

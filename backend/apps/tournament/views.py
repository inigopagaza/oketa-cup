"""Vistas de la app tournament (stub inicial)."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def results(request: HttpRequest) -> HttpResponse:
    """Página con todos los resultados del mundial agrupados por fase."""
    return render(request, "tournament/results.html", {})

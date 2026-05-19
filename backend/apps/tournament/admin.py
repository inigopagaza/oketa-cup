"""Admin del torneo."""

from django.contrib import admin

from .models import Match, NationalTeam, TournamentConfig


@admin.register(NationalTeam)
class NationalTeamAdmin(admin.ModelAdmin):
    """Admin para selecciones nacionales."""

    list_display = ("flag_emoji", "name", "code", "group", "price")
    list_filter = ("group",)
    search_fields = ("name", "code")
    ordering = ("group", "price")


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    """
    Admin para partidos.

    Permite introducir resultados directamente desde aquí.
    El campo is_finished activa el cálculo de puntuación.
    """

    list_display = (
        "home_team",
        "away_team",
        "phase",
        "group",
        "scheduled_at",
        "home_score",
        "away_score",
        "is_finished",
    )
    list_filter = ("phase", "group", "is_finished")
    list_editable = ("home_score", "away_score", "is_finished")
    ordering = ("scheduled_at",)
    date_hierarchy = "scheduled_at"


@admin.register(TournamentConfig)
class TournamentConfigAdmin(admin.ModelAdmin):
    """Admin para la configuración global del torneo."""

    def has_add_permission(self, request):  # type: ignore[override]
        """Solo permite un registro (singleton)."""
        return not TournamentConfig.objects.exists()

"""Admin del torneo."""

from django.contrib import admin, messages

from apps.pool.services.scoring import process_group_completion, process_match_result

from .models import Match, NationalTeam, TournamentConfig


@admin.register(NationalTeam)
class NationalTeamAdmin(admin.ModelAdmin):
    """Admin para selecciones nacionales."""

    list_display = ("flag_emoji", "name", "code", "group", "price")
    list_filter = ("group",)
    search_fields = ("name", "code")
    ordering = ("group", "price")


@admin.action(description="Recalcular puntuaciones de los partidos seleccionados")
def recalculate_match_scores(modeladmin, request, queryset):
    """Procesa los ScoreLogs de cada partido seleccionado (idempotente)."""
    finished = queryset.filter(is_finished=True)
    if not finished.exists():
        modeladmin.message_user(
            request,
            "Ningún partido seleccionado está marcado como finalizado.",
            messages.WARNING,
        )
        return
    total_logs = 0
    for match in finished:
        logs = process_match_result(match)
        total_logs += len(logs)
    modeladmin.message_user(
        request,
        f"Puntuaciones recalculadas: {finished.count()} partido(s), {total_logs} ScoreLog(s) generados.",
        messages.SUCCESS,
    )


@admin.action(
    description="Calcular clasificación de grupos de los partidos seleccionados"
)
def calculate_group_standings(modeladmin, request, queryset):
    """Calcula ADVANCE_GRP y TOP_GROUP para los grupos de los partidos seleccionados."""
    groups = (
        queryset.filter(phase=Match.Phase.GROUP)
        .exclude(group="")
        .values_list("group", flat=True)
        .distinct()
    )
    if not groups:
        modeladmin.message_user(
            request,
            "Ningún partido de grupos seleccionado.",
            messages.WARNING,
        )
        return
    total_logs = 0
    processed = []
    for group in sorted(groups):
        logs = process_group_completion(group)
        total_logs += len(logs)
        if logs:
            processed.append(group)
    if processed:
        modeladmin.message_user(
            request,
            f"Clasificación calculada para grupo(s) {', '.join(processed)}: {total_logs} ScoreLog(s) generados.",
            messages.SUCCESS,
        )
    else:
        modeladmin.message_user(
            request,
            "Ningún grupo está completamente terminado todavía.",
            messages.WARNING,
        )


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    """
    Admin para partidos.

    Permite introducir resultados directamente desde aquí.
    Tras actualizar los resultados del día, usa las acciones para calcular
    puntuaciones y clasificación de grupos.
    """

    actions = [recalculate_match_scores, calculate_group_standings]
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
        return not TournamentConfig.objects.exists()  # pyright: ignore[reportAttributeAccessIssue]

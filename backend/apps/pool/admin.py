"""Admin de la bolilla."""

from django.contrib import admin

from .models import Participant, ScoreLog


class ScoreLogInline(admin.TabularInline):
    """Muestra el historial de puntos dentro del Participant."""

    model = ScoreLog
    extra = 0
    readonly_fields = ("team", "match", "points_earned", "reason", "created_at")
    can_delete = False


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    """Admin para participantes de la bolilla."""

    list_display = ("user", "budget_used", "total_points", "has_confirmed")
    readonly_fields = ("total_points", "budget_used")
    filter_horizontal = ("teams",)
    inlines = [ScoreLogInline]

    @admin.display(description="Presupuesto usado")
    def budget_used(self, obj: Participant) -> str:
        return f"{obj.budget_used}🪙"

    @admin.display(description="Puntos totales")
    def total_points(self, obj: Participant) -> int:
        return obj.total_points

    @admin.display(boolean=True, description="Selección confirmada")
    def has_confirmed(self, obj: Participant) -> bool:
        return obj.user.has_confirmed_selection


@admin.register(ScoreLog)
class ScoreLogAdmin(admin.ModelAdmin):
    """Admin de solo lectura para el registro de puntuación."""

    list_display = ("participant", "team", "points_earned", "reason", "created_at")
    list_filter = ("team",)
    readonly_fields = (
        "participant",
        "team",
        "match",
        "points_earned",
        "reason",
        "created_at",
    )

    def has_add_permission(self, request):  # type: ignore[override]
        return False

    def has_change_permission(self, request, obj=None):  # type: ignore[override]
        return False

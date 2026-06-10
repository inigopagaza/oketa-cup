"""
Modelos de la bolilla.

Gestiona las selecciones de cada participante y el registro
histórico de puntos obtenidos.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext as _

from apps.tournament.models import Match, NationalTeam

# ── Códigos de motivo para ScoreLog ──────────────────────────────────────────

REASON_MATCH_WIN = "match_win"
REASON_MATCH_DRAW = "match_draw"
REASON_MATCH_LOSS = "match_loss"
REASON_GROUP_ADVANCE = "group_advance"
REASON_GROUP_FIRST = "group_first"
REASON_ADVANCE_PHASE = "advance_phase"
REASON_THIRD_PLACE = "third_place"
REASON_CHAMPION = "champion"
REASON_MVP = "mvp"
REASON_TOP_SCORER = "top_scorer"
REASON_BEST_GOALKEEPER = "best_goalkeeper"


def render_scorelog_reason(
    reason_code: str,
    reason_context: dict | None = None,
    fallback_reason: str = "",
) -> str:
    """Devuelve el motivo del ScoreLog en el idioma activo."""
    context = reason_context or {}

    if not reason_code:
        return fallback_reason

    if reason_code == REASON_MATCH_WIN:
        return _("Victoria vs %(rival)s") % {"rival": context.get("rival", "")}
    if reason_code == REASON_MATCH_DRAW:
        return _("Empate vs %(rival)s") % {"rival": context.get("rival", "")}
    if reason_code == REASON_MATCH_LOSS:
        return _("Derrota vs %(rival)s") % {"rival": context.get("rival", "")}
    if reason_code == REASON_GROUP_ADVANCE:
        return _("Clasificado desde grupo %(group)s") % {
            "group": context.get("group", "")
        }
    if reason_code == REASON_GROUP_FIRST:
        return _("1º de grupo %(group)s") % {"group": context.get("group", "")}
    if reason_code == REASON_ADVANCE_PHASE:
        phase_value = context.get("phase", "")
        try:
            phase_label = _(str(Match.Phase(phase_value).label)) if phase_value else ""
        except ValueError:
            phase_label = str(phase_value)
        return _("Clasificado a %(phase)s") % {"phase": phase_label}
    if reason_code == REASON_THIRD_PLACE:
        return _("3er puesto")
    if reason_code == REASON_CHAMPION:
        return _("¡Campeón del Mundial!")
    if reason_code == REASON_MVP:
        return _("Acertó el MVP del torneo")
    if reason_code == REASON_TOP_SCORER:
        return _("Acertó el Pichichi")
    if reason_code == REASON_BEST_GOALKEEPER:
        return _("Acertó el Zamora")

    return fallback_reason


class Participant(models.Model):
    """
    Participante en la bolilla.

    Relaciona un usuario con sus selecciones nacionales elegidas
    y sus predicciones de premios individuales.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="participant",
        verbose_name="Usuario",
    )
    teams = models.ManyToManyField(
        NationalTeam,
        blank=True,
        related_name="participants",
        verbose_name="Selecciones elegidas",
    )
    predicted_mvp = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="MVP predicho",
    )
    predicted_top_scorer = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Pichichi predicho",
    )
    predicted_best_goalkeeper = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Zamora predicho",
    )

    class Meta:
        verbose_name = "Participante"
        verbose_name_plural = "Participantes"

    def __str__(self) -> str:
        return str(self.user)

    @property
    def total_points(self) -> int:
        """Suma total de puntos acumulados en el ScoreLog."""
        return (
            self.score_logs.aggregate(total=models.Sum("points_earned"))["total"] or 0
        )

    @property
    def budget_used(self) -> int:
        """Monedas gastadas en las selecciones elegidas."""
        return self.teams.aggregate(total=models.Sum("price"))["total"] or 0


class ScoreLog(models.Model):
    """
    Registro de cada punto obtenido por un participante.

    Se crea automáticamente cuando se cierra un partido o se
    avanza en el torneo. Permite auditar el origen de cada punto.
    """

    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name="score_logs",
        verbose_name="Participante",
    )
    team = models.ForeignKey(
        NationalTeam,
        on_delete=models.CASCADE,
        related_name="score_logs",
        verbose_name="Selección",
    )
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="score_logs",
        verbose_name="Partido",
        help_text="Nulo para puntos de premios individuales o avance de fase",
    )
    points_earned = models.SmallIntegerField(verbose_name="Puntos obtenidos")
    reason_code = models.CharField(
        max_length=50,
        blank=True,
        default="",
        db_index=True,
        verbose_name="Código del motivo",
        help_text="Identificador estable para traducir el motivo.",
    )
    reason_context = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Contexto del motivo",
        help_text="Datos auxiliares para construir el motivo traducido.",
    )
    reason = models.CharField(
        max_length=200,
        verbose_name="Motivo",
        help_text="Descripción legible del motivo: 'Victoria vs Francia', 'Clasificado a cuartos'...",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro de puntuación"
        verbose_name_plural = "Registros de puntuación"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.participant} +{self.points_earned}pts — {self.display_reason}"

    @property
    def display_reason(self) -> str:
        """Motivo del punto traducido al idioma activo."""
        return render_scorelog_reason(
            self.reason_code,
            self.reason_context,
            self.reason,
        )

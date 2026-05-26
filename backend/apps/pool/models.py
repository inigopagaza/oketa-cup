"""
Modelos de la bolilla.

Gestiona las selecciones de cada participante y el registro
histórico de puntos obtenidos.
"""

from django.conf import settings
from django.db import models

from apps.tournament.models import Match, NationalTeam


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
        return f"{self.participant} +{self.points_earned}pts — {self.reason}"

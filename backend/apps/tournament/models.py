"""
Modelos del torneo.

Contiene las selecciones nacionales, los partidos y la configuración
global del torneo (presupuesto, ganadores de premios individuales).
"""

from django.db import models


class NationalTeam(models.Model):
    """
    Selección nacional participante en el Mundial.

    El precio define cuántas monedas cuesta incluirla en la bolilla.
    """

    name = models.CharField(max_length=100, verbose_name="Nombre")
    code = models.CharField(
        max_length=3,
        unique=True,
        verbose_name="Código FIFA",
        help_text="Código ISO de 3 letras, p.ej. ESP, ARG",
    )
    flag_emoji = models.CharField(
        max_length=10,
        blank=True,
        verbose_name="Emoji bandera",
        help_text="Emoji de la bandera, p.ej. 🇪🇸",
    )
    group = models.CharField(
        max_length=1,
        verbose_name="Grupo",
        help_text="Letra del grupo (A-L)",
    )
    price = models.PositiveSmallIntegerField(
        verbose_name="Precio (monedas)",
        help_text="Coste en monedas para elegir esta selección",
    )

    class Meta:
        verbose_name = "Selección nacional"
        verbose_name_plural = "Selecciones nacionales"
        ordering = ["group", "name"]

    def __str__(self) -> str:
        return f"{self.flag_emoji} {self.name} ({self.price}🪙)"


class Match(models.Model):
    """
    Partido del Mundial.

    Cubre todas las fases: grupos, octavos, cuartos, semis y final.
    Los resultados se introducen manualmente desde el panel de admin.
    """

    class Phase(models.TextChoices):
        GROUP = "GRP", "Fase de grupos"
        ROUND_OF_16 = "R16", "Octavos de final"
        QUARTER_FINAL = "QF", "Cuartos de final"
        SEMI_FINAL = "SF", "Semifinales"
        FINAL = "FIN", "Final"

    home_team = models.ForeignKey(
        NationalTeam,
        on_delete=models.CASCADE,
        related_name="home_matches",
        verbose_name="Local",
    )
    away_team = models.ForeignKey(
        NationalTeam,
        on_delete=models.CASCADE,
        related_name="away_matches",
        verbose_name="Visitante",
    )
    phase = models.CharField(
        max_length=3,
        choices=Phase,
        verbose_name="Fase",
    )
    group = models.CharField(
        max_length=1,
        blank=True,
        verbose_name="Grupo",
        help_text="Solo para partidos de fase de grupos",
    )
    scheduled_at = models.DateTimeField(verbose_name="Fecha y hora")
    home_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Goles local",
    )
    away_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Goles visitante",
    )
    is_finished = models.BooleanField(
        default=False,
        verbose_name="Finalizado",
    )

    class Meta:
        verbose_name = "Partido"
        verbose_name_plural = "Partidos"
        ordering = ["scheduled_at"]

    def __str__(self) -> str:
        score = f"{self.home_score}-{self.away_score}" if self.is_finished else "vs"
        return f"{self.home_team.name} {score} {self.away_team.name} ({self.get_phase_display()})"

    @property
    def home_won(self) -> bool | None:
        """Devuelve True si ganó el local, False si ganó el visitante, None si empate o no terminado."""
        if not self.is_finished or self.home_score is None or self.away_score is None:
            return None
        if self.home_score > self.away_score:
            return True
        if self.home_score < self.away_score:
            return False
        return None  # Empate

    @property
    def is_draw(self) -> bool:
        """Devuelve True si el partido terminó en empate."""
        if not self.is_finished or self.home_score is None or self.away_score is None:
            return False
        return self.home_score == self.away_score


class TournamentConfig(models.Model):
    """
    Configuración global del torneo (singleton).

    Solo debe existir un registro. Almacena el presupuesto por participante
    y los ganadores de los premios individuales (se rellenan al final).
    """

    budget = models.PositiveSmallIntegerField(
        default=220,
        verbose_name="Presupuesto por participante (monedas)",
    )
    real_mvp = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="MVP real del torneo",
    )
    real_top_scorer = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Pichichi real",
    )
    real_best_goalkeeper = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Zamora real (mejor portero)",
    )

    class Meta:
        verbose_name = "Configuración del torneo"
        verbose_name_plural = "Configuración del torneo"

    def __str__(self) -> str:
        return f"Configuración del torneo (presupuesto: {self.budget}🪙)"

    def save(self, *args, **kwargs) -> None:  # type: ignore[override]
        """Garantiza que solo exista un registro (patrón singleton)."""
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls) -> "TournamentConfig":
        """Obtiene la configuración, creándola si no existe."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

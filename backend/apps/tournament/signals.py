import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Match

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Match)
def propagate_match_winner(sender, instance: Match, **kwargs) -> None:
    """
    Punto de extensión: asignar automáticamente los equipos ganadores al
    siguiente partido del bracket (se implementará en una fase posterior).
    """
    if not instance.is_finished:
        return
    if instance.phase == Match.Phase.GROUP:
        return
    # Aquí se añadirá la lógica de avance de bracket en Fase 2.

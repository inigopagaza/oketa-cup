import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.pool.services.scoring import process_match_result

from .models import Match

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Match)
def on_match_saved(sender, instance: Match, **kwargs) -> None:
    """
    Cuando un partido se guarda con is_finished=True, dispara el cálculo
    de puntuación para todos los participantes que tienen equipos en ese partido.

    Idempotente: process_match_result borra y recalcula los ScoreLogs del
    partido cada vez que se invoca, por lo que es seguro corregir resultados.
    """
    if not instance.is_finished:
        return

    try:
        logs = process_match_result(instance)
        logger.info(
            "Partido %s procesado: %d ScoreLogs generados.", instance, len(logs)
        )
    except Exception:
        logger.exception("Error al procesar el resultado del partido %s.", instance)


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

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Match

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Match)
def propagate_match_winner(sender, instance: Match, **kwargs) -> None:
    """
    Propaga el ganador de un partido eliminatorio al slot correspondiente
    del siguiente partido del bracket.

    Se ejecuta cuando un partido queda marcado como finalizado y tiene
    ``next_match`` configurado. Requiere que el partido tenga resultado
    definitivo (no empate, ya que en eliminatorias siempre hay ganador
    incluyendo penaltis, aunque el marcador de penaltis no se registra
    en el modelo; el admin introduce el marcador final real).
    """
    if not instance.is_finished:
        return
    if instance.phase == Match.Phase.GROUP:
        return
    if not instance.next_match_id:
        return
    if instance.home_score is None or instance.away_score is None:
        return
    winner = instance.knockout_winner
    if winner is None:
        logger.warning(
            "Partido %s sin ganador resoluble (%s-%s, penaltis=%s); no propagado.",
            instance.pk,
            instance.home_score,
            instance.away_score,
            instance.penalties_winner,
        )
        return

    next_match = instance.next_match
    slot = instance.next_match_slot

    if slot == "home":
        next_match.home_team = winner  # type: ignore[union-attr]
    else:
        next_match.away_team = winner  # type: ignore[union-attr]

    next_match.save(update_fields=["home_team", "away_team"])  # type: ignore[union-attr]
    logger.info(
        "Bracket: %s → %s (%s slot %s)",
        instance,
        next_match,
        winner,
        slot,
    )

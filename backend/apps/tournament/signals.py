from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Match


@receiver(post_save, sender=Match)
def propagate_match_winner(sender, instance: Match, **kwargs):
    """
    Cuando un partido de eliminatoria se marca como finalizado,
    busca el siguiente partido que referencia a éste en match_label
    y lo deja listo para que el admin asigne los equipos ganadores.

    La lógica de avance automático completa (asignar FK de equipos al
    partido siguiente) se implementará en una fase posterior, una vez
    que se defina el bracket exacto en base de datos.
    """
    if not instance.is_finished:
        return
    if instance.phase == Match.Phase.GROUP:
        return
    # Punto de extensión: aquí se puede añadir lógica para avanzar
    # automáticamente los ganadores al siguiente partido del bracket.

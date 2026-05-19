"""
Modelos de usuario para OketaCup.

Extiende el usuario base de Django para añadir campos específicos
de la aplicación como el idioma preferido y el estado de selección.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Usuario personalizado de OketaCup.

    Hereda todos los campos estándar de Django (username, email,
    password, is_staff, etc.) y añade los específicos de la app.
    """

    class Language(models.TextChoices):
        SPANISH = "es", "Castellano"
        BASQUE = "eu", "Euskara"

    preferred_language = models.CharField(
        max_length=2,
        choices=Language,
        default=Language.SPANISH,
        verbose_name="Idioma preferido",
    )
    has_confirmed_selection = models.BooleanField(
        default=False,
        verbose_name="Ha confirmado selección",
        help_text="True cuando el participante ha elegido y bloqueado sus selecciones.",
    )

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self) -> str:
        return self.username

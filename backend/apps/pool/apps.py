"""Configuración de la app pool."""

from django.apps import AppConfig


class PoolConfig(AppConfig):
    """App de la bolilla: selecciones de participantes y puntuación."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.pool"
    verbose_name = "Bolilla"

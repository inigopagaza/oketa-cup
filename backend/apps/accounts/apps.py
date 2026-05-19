"""Configuración de la app accounts."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """App de gestión de usuarios y autenticación."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    verbose_name = "Cuentas de usuario"

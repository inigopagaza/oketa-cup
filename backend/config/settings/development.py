"""
Settings para el entorno de desarrollo local.

Activa DEBUG, usa SQLite opcional, y relaja restricciones de seguridad
para facilitar el desarrollo.
"""

from .base import *  # noqa: F401, F403

DEBUG = True

# En desarrollo aceptamos cualquier host
ALLOWED_HOSTS = ["*"]  # type: ignore[assignment]

# Mostrar emails en consola en lugar de enviarlos
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Django Debug Toolbar (opcional, añadir si se instala)
# INSTALLED_APPS += ["debug_toolbar"]
# MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + MIDDLEWARE

# CORS permisivo para desarrollo con React
CORS_ALLOW_ALL_ORIGINS = True

# Logging básico en consola
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "DEBUG",
    },
    "loggers": {
        "django.db.backends": {
            "handlers": ["console"],
            "level": "DEBUG",  # Muestra las queries SQL — útil para aprender
            "propagate": False,
        },
    },
}

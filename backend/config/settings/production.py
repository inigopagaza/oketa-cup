"""
Settings para producción.

Activa todas las medidas de seguridad. Requiere que las variables de
entorno estén correctamente configuradas en el servidor.
"""

import os

import dj_database_url

from .base import *  # noqa: F401, F403

DEBUG = False

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

csrf_trusted_origins = os.environ.get("CSRF_TRUSTED_ORIGINS", "")
if csrf_trusted_origins:
    CSRF_TRUSTED_ORIGINS = [
        origin.strip() for origin in csrf_trusted_origins.split(",") if origin.strip()
    ]
else:
    # Fallback útil: construir orígenes HTTPS desde ALLOWED_HOSTS.
    CSRF_TRUSTED_ORIGINS = [
        f"https://{host}" for host in ALLOWED_HOSTS if "*" not in host
    ]

database_url = os.environ.get("DATABASE_URL")
if database_url:
    try:
        DATABASES = {
            "default": dj_database_url.parse(
                database_url,
                conn_max_age=600,
                ssl_require=False,  # conexión interna Docker, sin SSL necesario
            )
        }
    except dj_database_url.ParseError:
        # Fallback seguro: usar configuración DB_* heredada de base.py
        pass

# Seguridad
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"

# Archivos estáticos
STATIC_ROOT = BASE_DIR / "staticfiles"  # noqa: F405

# Logs a stdout (Docker los captura)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
}

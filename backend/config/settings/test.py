"""
Settings para la ejecución de tests.

Usa SQLite en memoria para que los tests corran sin necesidad
de tener PostgreSQL arrancado. Más rápido y sin dependencias externas.
"""

from .base import *  # noqa: F401, F403

# Base de datos en memoria: sin necesidad de levantar Docker
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Clave secreta fija para tests (no importa la seguridad aquí)
SECRET_KEY = "test-secret-key-not-for-production"  # noqa: S105

# Sin debug en tests para detectar errores reales
DEBUG = False

# Sin logging para que la salida de pytest sea más limpia
LOGGING: dict = {}  # type: ignore[assignment]

# Contraseña simple para tests (más rápido que bcrypt)
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

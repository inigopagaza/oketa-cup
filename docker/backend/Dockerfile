# Imagen de producción del backend OketaCup
# Usa multi-stage build para mantener la imagen final ligera

# ── Etapa 1: builder ─────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

# uv para instalar dependencias rápidamente
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copiar ficheros de dependencias primero (mejor uso del cache de Docker)
COPY backend/pyproject.toml backend/uv.lock ./

# Instalar dependencias en /app/.venv sin dependencias de dev
RUN uv sync --frozen --no-dev

# ── Etapa 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

# Usuario no-root por seguridad (OWASP best practice)
RUN addgroup --system django && adduser --system --ingroup django django

WORKDIR /app

# Copiar el entorno virtual desde el builder
COPY --from=builder /app/.venv /app/.venv

# Copiar el código fuente
COPY backend/ .

# El entorno virtual va primero en el PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

# Recolectar estáticos en tiempo de build
RUN python manage.py collectstatic --noinput

# Cambiar al usuario no-root
USER django

EXPOSE 8000

# Gunicorn como servidor WSGI de producción
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]

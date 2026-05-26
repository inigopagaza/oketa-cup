# Imagen de producción del backend OketaCup
# Usa multi-stage build para mantener la imagen final ligera
# ── Stage 1: builder ───────────────────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /app
RUN pip install uv

COPY backend/pyproject.toml backend/uv.lock* ./
RUN uv sync --frozen --no-dev

# ── Stage 2: runtime ───────────────────────────────────────────────
FROM python:3.13-slim AS runtime

# Usuario sin root
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copiar solo el venv del builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copiar el código
COPY backend/ .

# Carpetas necesarias
RUN mkdir -p staticfiles media && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

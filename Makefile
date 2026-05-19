# Makefile — OketaCup
#
# Variables de entorno: backend/.env (nunca se sube a git)
# Copia backend/.env.example a backend/.env y rellena los valores antes de empezar.
#
# Uso habitual:
#   make up       → levanta la base de datos y Django
#   make down     → para y elimina los contenedores
#   make logs     → sigue los logs en tiempo real
#   make shell    → abre una shell en el contenedor de Django
#   make migrate  → aplica migraciones pendientes
#   make test     → ejecuta la suite de tests

COMPOSE      := docker compose -f docker/docker-compose.yml
ENV_FILE     := backend/.env
MANAGE       := $(COMPOSE) exec backend python manage.py

.PHONY: up up-d down logs shell migrate makemigrations test load-fixtures createsuperuser

## ── Ciclo de vida ─────────────────────────────────────────────────────────

up:
	$(COMPOSE) --env-file $(ENV_FILE) up

up-d:
	$(COMPOSE) --env-file $(ENV_FILE) up -d

down:
	$(COMPOSE) --env-file $(ENV_FILE) down

logs:
	$(COMPOSE) --env-file $(ENV_FILE) logs -f

## ── Django ────────────────────────────────────────────────────────────────

shell:
	$(COMPOSE) --env-file $(ENV_FILE) exec backend python manage.py shell

migrate:
	$(COMPOSE) --env-file $(ENV_FILE) exec backend python manage.py migrate

makemigrations:
	$(COMPOSE) --env-file $(ENV_FILE) exec backend python manage.py makemigrations

load-fixtures:
	$(COMPOSE) --env-file $(ENV_FILE) exec backend python manage.py load_fixtures --clear

createsuperuser:
	$(COMPOSE) --env-file $(ENV_FILE) exec backend python manage.py createsuperuser

## ── Calidad ───────────────────────────────────────────────────────────────

test:
	$(COMPOSE) --env-file $(ENV_FILE) exec backend pytest

## ── Producción (servidor) ─────────────────────────────────────────────────
## En producción las variables vienen del entorno del servidor, no de --env-file.
## El deploy en GitHub Actions inyecta los secretos vía SSH / docker compose.prod.yml.

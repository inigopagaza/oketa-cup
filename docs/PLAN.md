# OketaCup — Plan de Desarrollo

> **Proyecto**: Bolilla del Mundial 2026 entre amigos
> **Objetivo secundario**: Aprender a desarrollar con IA (GitHub Copilot)
> **Fecha de inicio**: Mayo 2026
> **Mundial 2026**: ~11 de junio de 2026

---

## Contexto y decisiones de arquitectura

| Decisión | Elección | Por qué |
|---|---|---|
| Repositorio | GitHub público, monorepo | Todo en un sitio, fácil de seguir |
| Backend | Django 6.x + DRF | Robusto, educativo, gran ecosistema Python |
| Frontend A | Django Templates + Alpine.js + Tailwind v4 | Sin build step, comparativo con React |
| Frontend B | React 19 + Vite + Zustand + react-i18next | SPA moderna, aprender comparando |
| Base de datos | PostgreSQL 16 | Estándar producción, bien integrado con Django |
| Auth | Sessions (templates) + JWT simplejwt (React) | Adecuado para cada paradigma |
| Gestión Python | `uv` + `pyproject.toml` | State of the art 2026, entornos rápidos |
| Calidad | `ruff`, `mypy`, `pytest-django`, `factory-boy` | Mejores prácticas Python |
| CI | GitHub Actions | Nativo con GitHub |
| Dev | Docker Compose | Entorno reproducible en cualquier máquina |
| Prod (futuro) | Nginx + Gunicorn + Proxmox | Self-hosted en casa |
| Idiomas | Castellano (es) + Euskara (eu) | Multilenguaje con Django i18n |
| Rama principal | `main` → producción, `develop` → integración | GitFlow simplificado |

---

## Estructura del proyecto

```
oketa-cup/
├── backend/                        # Proyecto Django (Python)
│   ├── config/
│   │   ├── settings/
│   │   │   ├── base.py             # Settings comunes a todos los entornos
│   │   │   ├── development.py      # Settings para desarrollo local
│   │   │   └── production.py       # Settings para producción (servidor)
│   │   ├── urls.py                 # Rutas URL raíz
│   │   ├── wsgi.py                 # Punto de entrada WSGI (producción)
│   │   └── asgi.py                 # Punto de entrada ASGI
│   ├── apps/
│   │   ├── accounts/               # Usuarios y autenticación
│   │   ├── tournament/             # Equipos, partidos, fases del torneo
│   │   └── pool/                   # Selecciones, puntuación, ScoreLog
│   │       └── services/
│   │           └── scoring.py      # Motor de puntuación (lógica de negocio)
│   ├── templates/                  # HTML templates (Frontend A)
│   ├── static/                     # CSS, JS, imágenes
│   ├── locale/                     # Traducciones es/eu (.po/.mo)
│   ├── .env.example                # Variables de entorno (plantilla)
│   ├── .venv/                      # Entorno virtual Python (no sube a git)
│   ├── pyproject.toml              # Toda la config Python aquí
│   └── manage.py                   # CLI de Django
├── frontend/                       # React SPA (Frontend B, Fase 4)
├── docker/
│   ├── docker-compose.yml          # Entorno de desarrollo
│   ├── docker-compose.prod.yml     # Entorno de producción
│   ├── backend/Dockerfile          # Imagen Docker del backend
│   └── nginx/nginx.conf            # Configuración Nginx (producción)
├── data/
│   ├── teams.json                  # 48 selecciones + precios (fixture)
│   └── fixtures.json               # 104 partidos (72 grupos + 32 eliminatoria)
├── docs/
│   ├── PLAN.md                     # Este fichero
│   ├── ARCHITECTURE.md             # Decisiones técnicas en detalle
│   └── DEPLOYMENT.md              # Guía de despliegue en Proxmox
├── .github/
│   └── workflows/
│       ├── ci.yml                  # Tests + lint en cada push/PR
│       └── deploy.yml              # Deploy automático a main (futuro)
├── .pre-commit-config.yaml         # Hooks locales antes de cada commit
├── Makefile                        # Comandos de desarrollo (make up/down/migrate/test…)
├── .gitignore
└── README.md
```

---

## Sistema de puntuación

### Fase de grupos

| Evento | Puntos |
|---|---|
| Victoria en partido de grupos | +3 |
| Empate en partido de grupos | +1 |
| Clasificar desde fase de grupos | +6 |
| Quedar 1º de grupo | +2 |

### Fases eliminatorias

| Evento | Puntos |
|---|---|
| Clasificar a octavos de final | +10 |
| Clasificar a cuartos de final | +15 |
| Clasificar a semifinales | +20 |
| Clasificar a la final | +25 |
| Ganar el Mundial | +25 |

### Premios individuales (al final del torneo)

| Premio | Puntos |
|---|---|
| Acertar el MVP del torneo | +20 |
| Acertar el Pichichi (máximo goleador) | +10 |
| Acertar el Zamora (mejor portero) | +5 |

### Presupuesto: 220 monedas por participante

---

### Arquitectura del cálculo de puntos

**Principio fundamental: el saldo de cada usuario es siempre `SUM(ScoreLog)`, nunca un acumulador.**

#### Flujo de cálculo — enfoque "bajo petición del admin"

> **Decisión de diseño (2026-05-20):** en lugar de calcular automáticamente via
> `post_save`, el cálculo se dispara manualmente desde el admin de Django.
> Esto elimina la complejidad de detectar cuándo está completo un grupo y evita
> cualquier problema de idempotencia con señales.

```
Admin actualiza resultados del día en la lista de Match
    → pulsa la admin action "Recalcular puntuaciones"
        → process_match_result(match) para cada partido seleccionado:
            1. DELETE ScoreLog WHERE match=este_partido   ← idempotencia garantizada
            2. Para cada equipo del partido:
               - buscar todos los Participant que lo tienen seleccionado
               - calcular puntos según resultado y fase
               - INSERT ScoreLog(participant, match, team, reason, points)
    → pulsa la admin action "Calcular clasificación de grupos"
        → process_group_completion(group) para cada grupo de los partidos seleccionados:
            1. DELETE ScoreLog de clasificación previos del grupo
            2. Calcular tabla (pts, GD, GF) con todos los partidos del grupo
            3. INSERT ScoreLog ADVANCE_GRP para 1º y 2º, TOP_GROUP para el 1º
    3. Score visible = SELECT SUM(points) FROM ScoreLog WHERE participant=X
```

Si el admin corrige un resultado → edita el partido → vuelve a pulsar "Recalcular" → ScoreLog del partido se borra y recalcula. Sin pérdida, sin duplicados.

#### Cuándo se calculan los puntos de grupo

| Evento | Cuándo | Admin action |
|---|---|---|
| Victoria en grupos | Admin pulsa "Recalcular puntuaciones" | `Recalcular puntuaciones` |
| Empate en grupos | Admin pulsa "Recalcular puntuaciones" | `Recalcular puntuaciones` |
| Clasificar desde grupos | Admin pulsa "Calcular clasificación de grupos" | `Calcular clasificación de grupos` |
| 1º de grupo | Admin pulsa "Calcular clasificación de grupos" | `Calcular clasificación de grupos` |
| Clasificar a octavos | Admin pulsa "Recalcular puntuaciones" | `Recalcular puntuaciones` |
| Clasificar a cuartos | Admin pulsa "Recalcular puntuaciones" | `Recalcular puntuaciones` |
| Clasificar a semifinales | Admin pulsa "Recalcular puntuaciones" | `Recalcular puntuaciones` |
| Clasificar a la final | Admin pulsa "Recalcular puntuaciones" | `Recalcular puntuaciones` |
| Ganar el Mundial | Admin pulsa "Recalcular puntuaciones" | `Recalcular puntuaciones` |

#### Estructura de ScoreLog

```python
class ScoreLog(Model):
    participant  # FK → Participant
    match        # FK → Match   ← clave para borrar/recalcular por partido
    team         # FK → NationalTeam
    reason       # CharField con los valores de la tabla anterior
    points       # IntegerField
```

---

## Precios de selecciones

**Grupo A:** México (36), Sudáfrica (23), Corea del Sur (41), Chequia (22)
**Grupo B:** Canadá (39), Bosnia (20), Qatar (15), Suiza (38)
**Grupo C:** Brasil (67), Marruecos (52), Haití (6), Escocia (26)
**Grupo D:** Estados Unidos (40), Paraguay (30), Australia (25), Turquía (35)
**Grupo E:** Alemania (60), Curazao (14), Costa de Marfil (33), Ecuador (37)
**Grupo F:** Países Bajos (55), Japón (44), Suecia (32), Túnez (8)
**Grupo G:** Bélgica (46), Egipto (34), Irán (29), Nueva Zelanda (7)
**Grupo H:** España (65), Cabo Verde (11), Arabia Saudí (24), Uruguay (50)
**Grupo I:** Francia (69), Senegal (43), Irak (13), Noruega (28)
**Grupo J:** Argentina (70), Argelia (27), Austria (42), Jordania (9)
**Grupo K:** Portugal (62), Congo R.D. (10), Uzbekistán (12), Colombia (47)
**Grupo L:** Inglaterra (64), Croacia (53), Ghana (31), Panamá (18)

---

## Fases de desarrollo

### ✅ FASE 0 — Fundamentos *(completada 2026-05-19)*

Objetivo: tener el entorno de desarrollo listo y el primer commit verde en CI.

- [x] Repositorio GitHub + rama `main` y `develop` (GitFlow simplificado)
- [x] Proyecto Python con `uv` + entorno virtual `.venv` + `pyproject.toml`
- [x] Estructura de carpetas del monorepo
- [x] Configuración de `ruff` (linter+formatter), `mypy` (tipado), `pytest` (tests)
- [x] `backend/.env` configurado localmente (copiar de `backend/.env.example`)
- [x] Docker Compose dev (PostgreSQL `oketa-cup-db` + Django `oketa-cup-container`)
- [x] **`Makefile`** en la raíz con comandos de desarrollo (`make up`, `make down`, `make migrate`, `make test`…)
  - Encapsula `--env-file backend/.env` para que nadie tenga que recordarlo
  - En producción las variables vienen del entorno del servidor, no de `--env-file`
- [x] `pre-commit` hooks instalados localmente (`ruff` lint + format)
- [x] GitHub Actions CI (lint + tests en cada push)
- [x] Primer `docker compose up` funcionando

### ✅ FASE 1 — Backend Core: modelos, fixtures y signals *(completada 2026-05-19)*

Objetivo: poder cargar el calendario completo y tener la base para la puntuación automática.

- [x] Modelos: `User`, `NationalTeam`, `Match`, `TournamentConfig`, `Participant`, `ScoreLog`
- [x] Migraciones 0001–0004 aplicadas:
  - `0001_initial` — modelos base
  - `0002_nullable_teams_match_label_third_place` — FKs nullable, `match_label`, fase `3PL`
  - `0003_add_round_of_32_phase` — fase `R32` (dieciseisavos, 48 equipos)
  - `0004_add_venue_to_match` — campo `venue` (sede del partido)
- [x] Fixture `data/teams.json` cargado en BD — 48 equipos, grupos A–L reales
- [x] `data/fixtures.json` — 104 partidos (72 grupos + 32 eliminatoria), todos con sede
- [x] Management command `load_fixtures` (flags: `--clear`, `--skip-knockout`)
- [x] `signals.py` creado con punto de extensión para avance automático del bracket
- [x] `apps.py` con `ready()` que importa signals
- [x] Motor de puntuación (`apps/pool/services/scoring.py`) — 15/15 tests pasan
- [x] Commit: `feat(tournament): add venue field, knockout phases, signals and load_fixtures` (771f5f1)
- [x] Commit: `feat(pool): connect post_save signal and fix idempotent scoring (DELETE+INSERT)` (8f3761e)

### 🔴 FASE 1B — Admin y lógica de selección *(en curso)*

Objetivo: poder entrar resultados desde el admin y calcular puntuación bajo petición.

- [x] `scoring.py`: idempotencia real — DELETE + INSERT al recalcular (soporta corrección de resultados)
- [x] `scoring.py`: `process_group_completion(group)` — calcula clasificación cuando todos los partidos del grupo terminan
- [x] `admin.py`: `MatchAdmin` con `list_editable` para `home_score`, `away_score`, `is_finished`
- [x] **Decisión: cálculo bajo petición** — admin actions en lugar de `post_save` automático
- [ ] `signals.py`: eliminar `on_match_saved` (cálculo ya no es automático)
- [ ] `admin.py`: action "Recalcular puntuaciones" → `process_match_result` por partido
- [ ] `admin.py`: action "Calcular clasificación de grupos" → `process_group_completion` por grupo
- [ ] `createsuperuser` + verificar flujo completo en admin
- [ ] Lógica de selección de equipos: `Participant` elige equipos, valida presupuesto ≤ 220, bloquea tras confirmar
- [ ] Tests pytest (cobertura > 70%)

### 🟡 FASE 2 — Frontend: Django Templates *(después del backend)*

Objetivo: flujo completo de usuario funcionando en móvil.

- [ ] Página de login (admin / usuario normal)
- [ ] Selección de equipos: grid, presupuesto en tiempo real (Alpine.js)
- [ ] Dashboard: clasificación, mis equipos, partidos del día
- [ ] Página de resultados del Mundial por fase
- [ ] Modo claro/oscuro (Tailwind + localStorage)
- [ ] Switcher de idioma es/eu
- [ ] Responsive mobile-first

### 🟢 FASE 3 — API REST *(post-lanzamiento)*

Objetivo: exponer todos los datos vía API para consumir desde React.

- [ ] DRF serializers + viewsets
- [ ] JWT auth (login, refresh, logout)
- [ ] Swagger UI con `drf-spectacular`
- [ ] Tests de endpoints

### 🟢 FASE 4 — Frontend: React *(post-lanzamiento, educativo)*

Objetivo: misma app que la Fase 2 pero en React, para comparar enfoques.

- [ ] Setup Vite + React 19 + TypeScript + Tailwind + react-i18next
- [ ] Axios con interceptores JWT
- [ ] Mismas páginas que la versión templates
- [ ] Comparativa documentada en `docs/ARCHITECTURE.md`

### 🔵 FASE 5 — Despliegue en casa *(cuando el servidor esté listo)*

Objetivo: app accesible en la red local / con dominio propio.

- [ ] Dockerfile multi-stage (build ligero, runtime sin root)
- [ ] `docker-compose.prod.yml` (Nginx + Gunicorn + PostgreSQL)
- [ ] SSL (Let's Encrypt o self-signed para red interna)
- [ ] GitHub Actions deploy: SSH + `docker compose up -d` en push a `main`
- [ ] Guía Proxmox en `docs/DEPLOYMENT.md`
- [ ] Backups automáticos de PostgreSQL

---

## Convenciones de Git

```
main          ← solo código listo para producción (merges desde develop)
develop       ← rama de integración (merges desde features)
feature/xxx   ← desarrollo de cada funcionalidad (desde develop)
fix/xxx       ← correcciones de bugs
chore/xxx     ← tareas de mantenimiento (deps, config...)
```

### Formato de commits (Conventional Commits)

```
feat: añadir selección de equipos con validación de presupuesto
fix: corregir cálculo de puntos en empate
chore: actualizar dependencias
docs: añadir guía de despliegue
test: añadir tests del motor de puntuación
refactor: extraer lógica de scoring a servicio
```

---

## Cómo trabajar con este proyecto

### Setup inicial (solo la primera vez)

```bash
# 1. Clonar el repo
git clone https://github.com/TU_USUARIO/oketa-cup.git
cd oketa-cup

# 2. Crear entorno virtual e instalar dependencias
cd backend
uv venv --python 3.13
source .venv/bin/activate   # En macOS/Linux
uv sync --all-groups

# 3. Configurar variables de entorno
cp backend/.env.example backend/.env
# Editar backend/.env con tus valores reales

# 4. Instalar hooks de pre-commit
cd backend && uv run pre-commit install && cd ..

# 5. Levantar servicios con Docker (usa el Makefile de la raíz)
make up-d

# 6. Crear las tablas en la BD
make migrate

# 7. Cargar datos iniciales
make load-fixtures
make createsuperuser
```

### Día a día

```bash
# Levantar todo (BD + Django)
make up

# Solo la BD (para correr Django fuera de Docker)
make up-d  # y luego:
source backend/.venv/bin/activate
cd backend && python manage.py runserver

# Parar contenedores
make down

# Aplicar migraciones
make migrate

# Pasar tests
make test

# Shell de Django
make shell

# Lint y formato (pre-commit lo hace automáticamente en cada commit)
cd backend && ruff check . && ruff format .
```

---

## Registro de progreso

| Fecha | Fase | Qué se hizo |
|---|---|---|
| 2026-05-19 | 0 | Setup inicial: git, uv, pyproject.toml, estructura de carpetas |
| 2026-05-19 | 0 | Modelos base: User, NationalTeam, Match, TournamentConfig, Participant, ScoreLog |
| 2026-05-19 | 0 | Motor de puntuación en `apps/pool/services/scoring.py` |
| 2026-05-19 | 0 | Docker Compose, Dockerfile multi-stage, GitHub Actions CI, pre-commit hooks |
| 2026-05-19 | 0 | Migraciones `0001_initial`, 48 equipos cargados, 15/15 tests ✅ (65% cobertura) |
| | | *(se irá completando)* |

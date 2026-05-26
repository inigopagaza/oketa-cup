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

### ✅ FASE 1B — Admin y lógica de puntuación *(completada 2026-05-20)*

Objetivo: poder entrar resultados desde el admin y calcular puntuación bajo petición.

- [x] `scoring.py`: idempotencia real — DELETE + INSERT al recalcular (soporta corrección de resultados)
- [x] `scoring.py`: `process_group_completion(group)` — calcula clasificación (ADVANCE_GRP +6, TOP_GROUP +2)
- [x] `admin.py`: `MatchAdmin` con `list_editable` para `home_score`, `away_score`, `is_finished`
- [x] **Decisión: cálculo bajo petición** — admin actions en lugar de `post_save` automático
- [x] `signals.py`: eliminado `on_match_saved`; solo queda punto de extensión para bracket (Fase 2)
- [x] `admin.py`: action *"Recalcular puntuaciones"* → `process_match_result` por partido seleccionado
- [x] `admin.py`: action *"Calcular clasificación de grupos"* → `process_group_completion` por grupo
- [x] Tests pytest: 19/19 pasan (incluye `TestGroupCompletion` con 4 casos)
- [x] Commit: `feat(admin): recalculate scores via admin actions instead of post_save signal` (37ac14b)

### ✅ FASE 1C — Selección de equipos y tests *(completada 2026-05-20)*

Objetivo: flujo completo de inscripción de participantes antes del inicio del Mundial.

- [x] Lógica de selección de equipos — `views.py`: `select_teams`, `confirm_selection`, `dashboard`
- [x] Validación de presupuesto ≤ 220 en `confirm_selection` (redisplay con error si supera)
- [x] Bloqueo de selección tras confirmar — `has_confirmed_selection = True` en `User`
- [x] Templates stub: `pool/dashboard.html`, `pool/select_teams.html`
- [x] Tests de views: 12 tests cubriendo todos los flujos (auth, redirección, validación, predicciones)
- [x] Cobertura total: 73.27% (objetivo > 70% ✅, `pool/views.py` 100%)
- [x] Commit: `feat(pool): add selection views tests and stub templates` (34f8047)

### ✅ FASE 2 — Frontend: Django Templates *(completada 2026-05-20)*

Objetivo: flujo completo de usuario funcionando en móvil.

- [x] `base.html`: layout con nav, modo claro/oscuro (Alpine.js + localStorage), responsive
- [x] `accounts/login.html`: formulario de login con manejo de errores
- [x] `pool/select_teams.html`: grid de equipos por grupo, contador de presupuesto en tiempo real (Alpine.js)
- [x] `pool/dashboard.html`: clasificación general, mis equipos con puntos, partidos del día
- [x] `tournament/results.html`: todos los partidos agrupados por fase con marcadores
- [x] Tailwind v4 CDN + Alpine.js CDN (sin build step)
- [x] Responsive mobile-first
- [x] Commit: `feat(frontend): Django Templates frontend with Tailwind v4 + Alpine.js` (aec1a34)

### ✅ FASE 2B — Multiidioma es/eu *(completada 2026-05-20)*

Objetivo: la interfaz en Castellano y Euskara; el idioma se recuerda entre sesiones.

**Decisión de diseño:** Django i18n nativo (`USE_I18N`, `LocaleMiddleware`, `.po/.mo`) en lugar
de soluciones de terceros. El cambio de idioma persiste en dos niveles:

1. **Sesión** — `LocaleMiddleware` lee la clave `_language` de la sesión HTTP.
2. **Perfil del usuario** — `User.preferred_language` (campo ya existente del modelo).
   Así si el usuario limpia las cookies su idioma preferido se recupera en el próximo login.

**Flujo al cambiar de idioma:**

```
Usuario pulsa [ES] o [EU] en el navbar
    → POST /i18n/set_language/?language=eu
        → set_language_view (wrapper de Django):
            1. Llama a django.views.i18n.set_language → guarda "_language" en sesión
            2. Si user.is_authenticated → user.preferred_language = "eu" → save()
        → redirect a request.path (misma página)
    → LocaleMiddleware en el siguiente request activa la traducción correspondiente
```

**Flujo al hacer login:**

```
login_view autentica al usuario
    → request.session["_language"] = user.preferred_language
    → el LocaleMiddleware activa automáticamente su idioma desde el primer request
```

**Implementación:**

- [x] `config/urls.py`: ruta `i18n/set_language/` apuntando a vista personalizada
- [x] `apps/accounts/views.set_language_view`: wrappea `django.views.i18n.set_language` y persiste en `user.preferred_language`
- [x] `apps/accounts/views.login_view`: tras autenticar, pone `request.session["_language"]` del perfil del usuario
- [x] `base.html`: switcher **ES | EU** en el navbar; botón activo en verde, otro en gris
- [x] `{% trans %}` en todos los templates: `base.html`, `login.html`, `dashboard.html`, `select_teams.html`, `results.html`
- [x] `tournament/views.py`: nombres de fase con `gettext_lazy` para que se traduzcan al servirse
- [x] `pool/select_teams.html`: predicciones individuales obligatorias (`required` + validación en vista); 🪙 solo para presupuesto, ✨ para puntos
- [x] `tournament/results.html`: tabs por fase (Alpine.js `x-show`) + separadores por jornada en fase de grupos
  - Agrupación por día: `regroup` con clave ISO `Y-m-d`; formato de fecha traducible (`l, d/m/Y` en ES → `Y/m/d` en EU)
- [x] `locale/eu/LC_MESSAGES/django.po`: traducciones Euskara completas
  - Nav: Emaitzak, Taldeak hautatu, Irten, Sartu
  - Dashboard: Nire taldeak, Gaurko partidak, Sailkapena, Puntu
  - Selección: Aukeratu zure taldeak, Aurrekontua, Hautaketa baieztatu
  - Resultados: Talde fasea, Hamaseirenak, Zortzirenak, Final-Laurdenak, Final-Erdiak, Finala, Amaituta
  - Fechas de jornada: formato `Y/m/d` (ej: 2026/06/11); grupos: `A Tald.`
- [x] `locale/eu/LC_MESSAGES/django.mo`: compilado con `msgfmt`
- [x] Commit: `feat(i18n): add es/eu language switcher with full translations` (e0bbb2f)
- [x] Settings ya tenían `USE_I18N=True`, `LANGUAGES=[("es","Castellano"),("eu","Euskara")]`, `LocaleMiddleware` y `LOCALE_PATHS` configurados desde la Fase 0

### ✅ FASE 2C — Panel de administración en la app *(completada 2026-05-20)*

Objetivo: el usuario `admin` gestiona resultados y recálculo de puntos directamente desde la web, sin pasar por el Django admin.

- [x] Admin bypassea la selección de equipos y entra directo al dashboard (`is_staff` salta el check `has_confirmed_selection`)
- [x] `pool/views.select_teams` y `confirm_selection`: redirigen al dashboard si `is_staff`
- [x] El admin no aparece en el ranking (filtro `user__is_staff=False` en la query de participantes)
- [x] `dashboard.html`: panel naranja de administración visible solo para `is_staff` con todos los textos traducidos (es/eu)
  - Formulario por cada partido pasado no finalizado → `home_score`, `away_score`, checkbox "Finalizado"
  - Al guardar con "Finalizado" marcado, llama automáticamente a `process_match_result`
  - Botón "🔄 Recalcular puntuaciones" → recalcula todos los partidos finalizados (idempotente)
- [x] `tournament/views.admin_set_result` (POST, staff-only): actualiza resultado y procesa puntuación
- [x] `tournament/views.admin_recalculate` (POST, staff-only): recalcula todos los finalizados
- [x] `tournament/urls.py`: rutas `tournament/admin/resultado/<id>/` y `tournament/admin/recalcular/`
- [x] `locale/eu/LC_MESSAGES/django.po`: traducciones del panel admin al Euskara

### ✅ FASE 2C-fix — Correcciones al panel de administración *(2026-05-20)*

Objetivo: corregir bugs detectados durante la simulación del primer día de partidos.

**Bugs encontrados y solucionados:**

- [x] **Duplicados en clasificación** — `Participant.Meta.ordering = ["-score_logs__points_earned"]` hacía un JOIN SQL con la tabla `score_logs` que devolvía N filas por participante (una por cada ScoreLog). El `sorted()` en Python los mostraba todos, apareciendo el mismo usuario múltiples veces.
  - Solución: eliminado el `ordering` problemático del `Meta`; añadido `.distinct()` al queryset de ranking en `pool/views.dashboard`

- [x] **Sin opción de corregir resultados finalizados** — El filtro `is_finished=False` hacía que los partidos ya cerrados desaparecieran del panel sin posibilidad de corrección.
  - Solución: nueva sección "Corregir resultados finalizados" (borde verde) en el panel naranja, con formulario idéntico al de introducir resultados pero con el checkbox "Finalizado" pre-marcado. Al guardar, `process_match_result` borra los ScoreLogs previos del partido (idempotencia ya implementada) y los recrea con el resultado corregido.
  - `pool/views.dashboard`: añadido `finished_matches` al contexto (partidos `is_finished=True`, ordenados por fecha descendente)
  - `locale/eu/LC_MESSAGES/django.po`: añadidas traducciones de "Corregir resultados finalizados" y "Corregir"

---

---

### ✅ FASE 2E — Adjudicación manual de premios individuales *(2026-05-20)*

Objetivo: permitir al admin adjudicar los puntos de MVP, Pichichi y Zamora al final del torneo, de forma manual para gestionar errores ortográficos en las predicciones.

**Motivación:** la función `award_individual_prizes()` existente hacía matching exacto de strings, lo que implicaba que cualquier falta de ortografía o variación en la escritura del nombre dejaba sin puntos al participante. El admin necesita decidir quién acertó independientemente de cómo lo escribió.

**Cambios implementados:**

- [x] **`tournament/views.py`** — nueva vista `admin_award_prizes` (POST):
  - Lee `real_mvp`, `real_top_scorer` y `real_best_goalkeeper` del formulario y los guarda en `TournamentConfig`
  - Para cada premio: borra los `ScoreLog` previos con `match=None` y la razón correspondiente (idempotencia total)
  - Crea nuevos `ScoreLog` para los participantes marcados con checkboxes por el admin
  - Exporta constantes `_REASON_MVP`, `_REASON_TOP_SCORER`, `_REASON_GOALKEEPER` para reutilización en `pool/views.py`
  - Puntos: MVP=20, Pichichi=10, Zamora=5 (de `scoring.py`)

- [x] **`tournament/urls.py`** — nueva ruta `admin/premios/` → `admin_award_prizes`, name=`admin_award_prizes`

- [x] **`pool/views.dashboard`** — añadidos al contexto (solo si `is_staff`):
  - `tournament_config`: objeto `TournamentConfig` con los nombres reales guardados previamente
  - `prize_participants`: lista de dicts con cada participante y booleanos `mvp_correct`, `top_scorer_correct`, `goalkeeper_correct` (según ScoreLogs existentes)

- [x] **`templates/pool/dashboard.html`** — nueva sección "Premios individuales" en el panel naranja (antes del botón Recalcular):
  - 3 bloques (MVP / Pichichi / Zamora): input texto para el ganador real + lista de participantes con checkboxes
  - Muestra en cada checkbox: username + predicción del participante entre paréntesis
  - Los participantes ya adjudicados aparecen pre-marcados y con texto verde
  - Botón "Adjudicar premios" → POST a `tournament:admin_award_prizes`

- [x] **`locale/eu/LC_MESSAGES/django.po`** — traducciones al euskera de todos los strings nuevos compiladas en `.mo`

**Funcionamiento:**
1. Admin abre el dashboard, ve la sección "Premios individuales"
2. Escribe el nombre real del MVP/Pichichi/Zamora (o lo deja si ya lo había guardado antes)
3. Marca manualmente quién lo acertó (puede ser 0, 1 o varios participantes)
4. Pulsa "Adjudicar premios" → se eliminan adjudicaciones previas y se crean las nuevas
5. Los puntos aparecen en el ranking inmediatamente

---

### ✅ FASE 2D — Configuración de tipo estático (Pylance/Pyright) *(2026-05-20)*

Objetivo: eliminar falsos positivos del linter en VS Code sin comprometer el código.

**Contexto:** Al configurar el intérprete Python del venv, Pylance empezó a analizar el código y
reportó errores en los modelos y vistas de Django — todos falsos positivos derivados de que Django
genera atributos dinámicamente en runtime (mediante su metaclass) que los type checkers estáticos
no pueden inferir sin ayuda.

**Atributos afectados:**
- `Model.objects` → añadido por la metaclass de Django; definido en `django-stubs` pero requiere el plugin de mypy para inferencia completa
- `home_team_id`, `away_team_id` → generados automáticamente por Django para campos FK con `null=True`
- `get_phase_display()` → generado por Django para campos con `choices`

**Solución aplicada:**
- [x] `.vscode/settings.json`: configura el intérprete (`backend/.venv/bin/python`), `extraPaths`, `typeCheckingMode: basic`
- [x] `pyrightconfig.json`: `venvPath/venv` apuntando al venv de uv, `reportAttributeAccessIssue: "none"` para silenciar falsos positivos de atributos dinámicos de Django
- [x] `# pyright: ignore[reportAttributeAccessIssue]` en las líneas afectadas de `models.py`, `admin.py` y `views.py` (defensa en profundidad)
- [x] `django-stubs 6.0.4` ya estaba instalado como dev dependency; los errores desaparecen tras recargar la ventana de VS Code (`Developer: Reload Window`)

**Nota:** `django-stubs` está diseñado para mypy (usa `mypy_django_plugin`). Pyright/Pylance no soporta plugins de mypy, por lo que algunos atributos dinámicos de Django siempre requerirán supresión manual o `pyrightconfig.json`.

### � FASE 3A — Panel de gestión separado *(próxima)*

Objetivo: sacar la gestión de administración del dashboard de usuario a una URL dedicada, dejando el dashboard limpio para participantes y el panel exclusivo para staff.

**Motivación:** el dashboard estaba mezclando dos responsabilidades distintas — la vista de participante (ranking, puntos, equipos) y la gestión de admin (resultados, premios, bracket). Con el Mundial en marcha, el panel crecerá más y necesita su propio espacio.

**Decisión de diseño:**

| Rol | Pantalla |
|-----|---------|
| Participante | `/` → dashboard: ranking, mis puntos, mis equipos, partidos del día |
| Staff | `/gestion/` → panel de gestión: resultados, premios, bracket |

**Implementación prevista:**

- [ ] Nueva app `management` (o nueva sección en `tournament`) con URL base `/gestion/`
- [ ] `GestionView` (staff-only, `login_required + is_staff`): resumen del estado del torneo
- [ ] `/gestion/partidos/` — entrada y corrección de resultados por fase
- [ ] `/gestion/premios/` — adjudicación de MVP, Pichichi, Zamora
- [ ] Migrar el panel naranja del `dashboard.html` a los templates de gestión
- [ ] Navbar: botón "Panel de gestión" visible solo para `is_staff`
- [ ] Traducciones es/eu para todos los strings nuevos

---

### 🔲 FASE 3B — Configuración manual de dieciseisavos *(próxima)*

Objetivo: permitir al admin introducir los 16 cruces de dieciseisavos una vez la FIFA los oficializa, sin necesitar lógica de desempate en el sistema.

**Decisión de diseño — por qué manual:**

El Mundial 2026 tiene 12 grupos con 4 equipos cada uno. Ascienden:
- Los 2 primeros de cada grupo (24 equipos)
- Los 8 mejores terceros (de 12 grupos posibles)

La posición de los 8 mejores terceros en el cuadro depende de **qué grupos** provengan, según una tabla predefinida por la FIFA. El desempate entre terceros con los mismos puntos usa diferencia de goles, goles a favor, tarjetas y fair play — ninguno de esos datos se trackea en este sistema. Por tanto, **la generación automática del cuadro de dieciseisavos no es viable** sin replicar toda la lógica FIFA.

**Solución: admin introduce los 16 cruces manualmente** una sola vez, cuando la FIFA los publica (tras terminar todos los grupos).

**Implementación prevista:**

- [ ] `/gestion/eliminatorias/` — vista con el estado del cuadro por rondas
- [ ] Formulario en `/gestion/eliminatorias/dieciseisavos/` para asignar `home_team` y `away_team` a cada uno de los 16 partidos de fase `R32` ya existentes en BD
- [ ] Los 16 slots de `R32` ya existen en `fixtures.json` con `team_home=null`, `team_away=null`
- [ ] Validación: solo permite asignar equipos que hayan completado la fase de grupos
- [ ] Traducciones es/eu

---

### 🔲 FASE 3C — Propagación automática de ganadores *(próxima)*

Objetivo: a partir de octavos de final, cuando el admin introduce un resultado, el ganador se propaga automáticamente al partido siguiente del cuadro sin intervención manual.

**Decisión de diseño:**

| Ronda | Configuración de enfrentamientos |
|-------|----------------------------------|
| Grupos | Precargados en `fixtures.json` ✅ |
| Dieciseisavos (R32) | Admin manual (Fase 3B) |
| Octavos (R16) en adelante | **Automático** via signal |

**Cómo funciona:**

Los slots de octavos, cuartos, semis y final ya existen en BD con `team_home=null` y `team_away=null`. Cada partido de R32 tiene un `next_match_id` implícito según la estructura del cuadro (slot fijo del bracket del Mundial 2026). Al registrar el resultado de un partido:

```
Admin guarda resultado partido R32 (is_finished=True)
    → signal post_save en Match detecta la ronda
        → determina el next_match según tabla de bracket hardcodeada
        → actualiza next_match.home_team o away_team con el ganador
    → el cuadro se actualiza automáticamente para todos los participantes
```

**Implementación prevista:**

- [ ] Tabla de bracket en `tournament/bracket.py` — mapping `match_id → (next_match_id, slot)` para las fases R32 → R16 → QF → SF → F
- [ ] Signal `on_knockout_result_saved` en `signals.py`: detecta partidos `is_finished=True` con fase R32+, llama a `advance_winner_in_bracket(match)`
- [ ] `advance_winner_in_bracket(match)` en `scoring.py` o `bracket.py`: determina ganador (no hay empates en eliminatorias) y actualiza el slot en el siguiente partido
- [ ] Vista `/gestion/eliminatorias/` muestra el cuadro completo con el estado actual
- [ ] Tests: propagación correcta en cada ronda, idempotencia al sobrescribir resultado
- [ ] Traducciones es/eu

---

### 🔵 FASE 5 — Despliegue en casa *(siguiente)*

Objetivo: app accesible desde internet con dominio propio, desplegada en servidor Proxmox doméstico.
Guía paso a paso completa: [`docs/DEPLOY.md`](DEPLOY.md)

- [ ] `docker-compose.prod.yml` (Nginx + Gunicorn + PostgreSQL, sin dev-tools)
- [ ] Dockerfile multi-stage (build ligero, runtime sin root)
- [ ] `config/settings/production.py` con variables de entorno
- [ ] Proxmox VE instalado + LXC Ubuntu 22.04 con Docker
- [ ] Cloudflare Tunnel (acceso externo sin abrir puertos, SSL automático)
- [ ] Dominio gratuito (DuckDNS o EU.org) vinculado a Cloudflare
- [ ] GitHub Actions `deploy.yml`: push a `main` → SSH al servidor → `docker compose up -d`
- [ ] Backups automáticos de PostgreSQL con `pg_dump` + cron
- [ ] Firewall (UFW) + fail2ban en el servidor

### 🟢 FASE 6 — API REST *(post-lanzamiento)*

Objetivo: exponer todos los datos vía API para consumir desde React.

- [ ] DRF serializers + viewsets
- [ ] JWT auth (login, refresh, logout)
- [ ] Swagger UI con `drf-spectacular`
- [ ] Tests de endpoints

### 🟢 FASE 7 — Frontend: React *(post-lanzamiento, educativo)*

Objetivo: misma app que la Fase 2 pero en React, para comparar enfoques.

- [ ] Setup Vite + React 19 + TypeScript + Tailwind + react-i18next
- [ ] Axios con interceptores JWT
- [ ] Mismas páginas que la versión templates
- [ ] Comparativa documentada en `docs/ARCHITECTURE.md`

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

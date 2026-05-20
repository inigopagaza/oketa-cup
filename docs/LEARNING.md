# LEARNING.md — Aprende con OketaCup

> Una guía para entender **cómo y por qué** está construido este proyecto, pensada para alguien que quiere convertirse en un mejor programador.

---

## Índice

1. [¿Qué es este proyecto?](#1-qué-es-este-proyecto)
2. [Estructura de carpetas](#2-estructura-de-carpetas)
3. [El entorno virtual y uv](#3-el-entorno-virtual-y-uv)
4. [pyproject.toml — la única fuente de verdad](#4-pyprojecttoml--la-única-fuente-de-verdad)
5. [El fichero .env y python-decouple](#5-el-fichero-env-y-python-decouple)
6. [Django: configuración por entorno](#6-django-configuración-por-entorno)
7. [Modelos y la base de datos](#7-modelos-y-la-base-de-datos)
8. [URLs y vistas](#8-urls-y-vistas)
9. [Templates y Tailwind CSS](#9-templates-y-tailwind-css)
10. [Archivos estáticos y WhiteNoise](#10-archivos-estáticos-y-whitenoise)
11. [Internacionalización (i18n)](#11-internacionalización-i18n)
12. [Signals de Django](#12-signals-de-django)
13. [Management commands](#13-management-commands)
14. [Docker y Docker Compose](#14-docker-y-docker-compose)
15. [El Makefile](#15-el-makefile)
16. [Ruff: linter y formatter](#16-ruff-linter-y-formatter)
17. [Pre-commit hooks](#17-pre-commit-hooks)
18. [Tests con pytest-django](#18-tests-con-pytest-django)
19. [Cobertura de código](#19-cobertura-de-código)
20. [GitHub Actions — CI/CD](#20-github-actions--cicd)
21. [Flujo de trabajo con Git](#21-flujo-de-trabajo-con-git)
22. [Flujo completo de una petición HTTP](#22-flujo-completo-de-una-petición-http)
23. [Errores comunes y por qué ocurren](#23-errores-comunes-y-por-qué-ocurren)
24. [Herramientas que deberías conocer](#24-herramientas-que-deberías-conocer)

---

## 1. ¿Qué es este proyecto?

**OketaCup** es una aplicación web de quiniela para el Mundial de Fútbol 2026. Los participantes eligen selecciones nacionales antes de empezar el torneo, y ganan puntos según cómo van avanzando esas selecciones.

Es un proyecto **Django monolítico** (sin separar frontend y backend): Django genera el HTML directamente usando templates, sin un framework de JavaScript en el servidor. Usa Alpine.js para la interactividad mínima (tabs, confirmaciones) y Tailwind CSS para los estilos, ambos cargados desde CDN sin build step.

**Por qué esta arquitectura:**
Para una app pequeña con pocos usuarios activos, un monolito Django es la opción más simple y mantenible. Añadir React o Vue solo añadiría complejidad sin beneficio real.

---

## 2. Estructura de carpetas

```
oketa-cup/                         ← raíz del repositorio
├── .github/workflows/ci.yml       ← automatización de tests en GitHub
├── .pre-commit-config.yaml        ← hooks que se ejecutan antes de cada commit
├── .ruff_cache/                   ← caché de ruff (ignorado en git)
├── Makefile                       ← comandos abreviados del proyecto
├── docker/
│   ├── docker-compose.yml         ← orquestación de contenedores (dev)
│   ├── backend/Dockerfile         ← imagen Docker del backend
│   └── nginx/                     ← proxy inverso (producción)
├── docs/                          ← documentación del proyecto
│   ├── PLAN.md
│   ├── DEPLOY.md
│   └── LEARNING.md  ← estás aquí
└── backend/                       ← código Django (todo lo de Python)
    ├── .env                       ← secretos locales (NO se sube a git)
    ├── .env.example               ← plantilla del .env para otros devs
    ├── .python-version            ← versión de Python que usa uv
    ├── pyproject.toml             ← dependencias, linters, configuración de tests
    ├── uv.lock                    ← versiones exactas de todos los paquetes
    ├── manage.py                  ← punto de entrada CLI de Django
    ├── conftest.py                ← fixtures globales de pytest
    ├── apps/                      ← código de negocio dividido en apps
    │   ├── accounts/              ← modelo User y autenticación
    │   ├── tournament/            ← selecciones, partidos, bracket
    │   └── pool/                  ← lógica de la quiniela y puntuación
    ├── config/                    ← configuración de Django
    │   ├── settings/
    │   │   ├── base.py            ← settings comunes a todos los entornos
    │   │   ├── development.py     ← settings solo para desarrollo local
    │   │   ├── test.py            ← settings para los tests (SQLite en memoria)
    │   │   └── production.py      ← settings para el servidor real
    │   ├── urls.py                ← rutas raíz
    │   └── wsgi.py / asgi.py      ← puntos de entrada para el servidor web
    ├── data/                      ← ficheros JSON con los datos del torneo
    │   ├── teams.json             ← 48 selecciones con precio y grupo
    │   └── fixtures.json          ← 104 partidos del Mundial
    ├── locale/
    │   └── eu/LC_MESSAGES/
    │       ├── django.po          ← traducciones al euskera (texto editable)
    │       └── django.mo          ← traducciones compiladas (binario)
    ├── static/                    ← CSS y JS propios del proyecto
    ├── staticfiles/               ← generado por collectstatic (no editar)
    └── templates/                 ← HTML de la app
        ├── base.html              ← layout compartido por todas las páginas
        ├── management/gestion.html
        ├── tournament/
        └── pool/
```

**Por qué `backend/` separado de la raíz:**
La raíz contiene infraestructura (Docker, Makefile, GitHub Actions). El código Python vive en `backend/`. Esto facilita desplegar solo el backend en el servidor sin arrastrar ficheros de infra.

---

## 3. El entorno virtual y uv

### ¿Qué es un entorno virtual?

Python instala paquetes de forma global en el sistema. Si dos proyectos necesitan versiones distintas de Django, hay conflicto. Un **entorno virtual** es una copia aislada de Python con sus propios paquetes, solo para ese proyecto.

### ¿Qué es uv?

[uv](https://github.com/astral-sh/uv) es un gestor de paquetes y entornos virtuales para Python, escrito en Rust. Es entre 10 y 100 veces más rápido que `pip` + `venv`. Creado por [Astral](https://astral.sh/), los mismos que crearon `ruff`.

```bash
# Crear el entorno e instalar todo (prod + dev)
cd backend
uv sync --all-groups

# Ejecutar cualquier cosa dentro del entorno sin activarlo
uv run pytest
uv run python manage.py migrate
uv run ruff check .
```

**Por qué `uv run` en lugar de activar el entorno:**
`uv run <comando>` ejecuta ese comando dentro del entorno virtual automáticamente, sin necesidad de hacer `source .venv/bin/activate` primero. Menos pasos, menos errores.

### El fichero `uv.lock`

`uv.lock` registra las versiones **exactas** de todas las dependencias (incluyendo las transitivas, las dependencias de las dependencias). Garantiza que todos los desarrolladores y el CI usen exactamente los mismos paquetes.

```
# Correcto: sube uv.lock a git
git add uv.lock

# Nunca hagas esto manualmente — uv lo gestiona solo
rm uv.lock
```

### El fichero `.python-version`

Contiene simplemente `3.13`. Le dice a uv qué versión de Python usar en este directorio. Equivalente a `.nvmrc` para Node.js.

---

## 4. pyproject.toml — la única fuente de verdad

`pyproject.toml` es el fichero estándar moderno de Python (PEP 517/518/621) que reemplaza a `setup.py`, `setup.cfg`, `requirements.txt`, `.flake8`, `.isort.cfg`, etc. Todo en un solo sitio.

### Secciones importantes

```toml
[project]
# Metadatos del proyecto y dependencias de producción
dependencies = [
    "django>=6.0.5",
    "psycopg2-binary>=2.9.12",   # Driver de PostgreSQL
    "python-decouple>=3.8",       # Leer variables de entorno
    "whitenoise>=6.12.0",         # Servir archivos estáticos
    "gunicorn>=26.0.0",           # Servidor WSGI de producción
    ...
]

[dependency-groups]
dev = [
    "pytest>=9.0.3",              # Framework de tests
    "pytest-django>=4.12.0",      # Integración de pytest con Django
    "pytest-cov>=7.1.0",          # Cobertura de código
    "ruff>=0.15.13",              # Linter + formatter
    "pre-commit>=4.6.0",          # Automatizar checks antes de commit
    ...
]
```

Las dependencias de dev no se instalan en producción (Docker usa `uv sync --no-dev`).

```toml
[tool.pytest.ini_options]
# Qué settings usar para los tests
DJANGO_SETTINGS_MODULE = "config.settings.test"
# Dónde buscar los tests
testpaths = ["apps"]
# Opciones por defecto de pytest (cobertura automática)
addopts = "--cov=apps --cov-report=term-missing --cov-report=xml -v"
```

```toml
[tool.coverage.report]
fail_under = 60   # Si la cobertura baja del 60%, pytest falla
```

---

## 5. El fichero .env y python-decouple

Los secretos (contraseñas, claves de API, SECRET_KEY de Django) **nunca se escriben directamente en el código**. Si los subes a git, cualquiera con acceso al repositorio los puede ver.

La solución: un fichero `.env` que no se sube a git (está en `.gitignore`).

```bash
# backend/.env (NUNCA en git)
SECRET_KEY=mi-clave-secreta-muy-larga
DB_PASSWORD=mi-password-de-postgres
DB_HOST=localhost
```

`python-decouple` lee este fichero y expone los valores:

```python
# config/settings/base.py
from decouple import Csv, config

SECRET_KEY = config("SECRET_KEY")               # Requerido: falla si no existe
DB_PASSWORD = config("DB_PASSWORD")             # Requerido
ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv(), default="")  # Opcional
```

**¿Cómo se enteran los demás desarrolladores de qué variables hacen falta?**
Con el fichero `.env.example`:

```bash
# .env.example (SÍ en git, sin valores reales)
SECRET_KEY=cambia-esto-por-una-clave-secreta-larga-y-aleatoria
DB_PASSWORD=cambia-esto-por-tu-password
```

El primer paso de cualquier desarrollador nuevo es: `cp .env.example .env` y rellenar los valores.

---

## 6. Django: configuración por entorno

En lugar de un solo `settings.py`, hay cuatro ficheros en `config/settings/`:

| Fichero | Cuándo se usa | Características |
|---|---|---|
| `base.py` | Siempre (importado por todos) | Configuración común |
| `development.py` | Desarrollo local | DEBUG=True, logs de SQL |
| `test.py` | Al correr pytest | SQLite en memoria, sin logs |
| `production.py` | Servidor real | DEBUG=False, seguridad máxima |

Cada fichero empieza con `from .base import *` para heredar la configuración base y luego solo sobreescribe lo que cambia.

**Por qué no usar solo `DEBUG = True/False`:**
La BD de tests usa SQLite en memoria (sin necesidad de tener PostgreSQL levantado). La BD de desarrollo usa PostgreSQL real. En producción hay configuraciones adicionales de seguridad. Un solo fichero se volvería un `if DEBUG:` caótico.

### `BASE_DIR`

```python
BASE_DIR = Path(__file__).resolve().parent.parent.parent
```

`__file__` → `/app/config/settings/base.py`
`.parent` → `/app/config/settings/`
`.parent` → `/app/config/`
`.parent` → `/app/` (= directorio `backend/`)

`BASE_DIR` es el punto de referencia para todas las rutas del proyecto. Se usa así:

```python
TEMPLATES = [{"DIRS": [BASE_DIR / "templates"]}]
LOCALE_PATHS = [BASE_DIR / "locale"]
STATIC_ROOT = BASE_DIR / "staticfiles"
```

---

## 7. Modelos y la base de datos

### ¿Qué es un modelo Django?

Un modelo es una clase Python que representa una tabla en la base de datos. Django genera el SQL automáticamente.

```python
class NationalTeam(models.Model):
    name = models.CharField(max_length=100)
    price = models.PositiveSmallIntegerField()
    group = models.CharField(max_length=1)
```

Esto crea una tabla con columnas `id` (autoincremental), `name`, `price`, `group`.

### Migraciones

Cuando cambias un modelo, Django no toca la BD automáticamente. Tienes que crear y aplicar una migración:

```bash
# Genera el fichero de migración
uv run python manage.py makemigrations

# Aplica los cambios a la BD
uv run python manage.py migrate
```

Los ficheros de migración (en `apps/*/migrations/`) **se suben a git**. Son el historial de cambios del esquema de la BD.

### Tipos de relaciones

```python
# ForeignKey: muchos Match a una NationalTeam
home_team = models.ForeignKey(NationalTeam, on_delete=models.SET_NULL, null=True)

# OneToOneField: un Participant por User
user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

# ManyToManyField: un Participant tiene muchos NationalTeams
teams = models.ManyToManyField(NationalTeam, blank=True)
```

### `AUTH_USER_MODEL = "accounts.User"`

Django tiene un modelo `User` por defecto. En lugar de usarlo directamente, lo extendemos con `AbstractUser` para añadir campos propios (`preferred_language`, `has_confirmed_selection`). La configuración `AUTH_USER_MODEL` le dice a Django qué modelo usar.

**Regla de oro:** define esto antes de la primera migración. Cambiarlo después es muy doloroso.

---

## 8. URLs y vistas

### Estructura de URLs

```
config/urls.py (raíz)
├── /admin/           → Django admin
├── /accounts/        → apps.accounts.urls
├── /pool/            → apps.pool.urls
└── /                 → apps.tournament.urls
```

```python
# config/urls.py
urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("pool/", include("apps.pool.urls", namespace="pool")),
    path("", include("apps.tournament.urls", namespace="tournament")),
]
```

**Namespaces** (`namespace="tournament"`): permiten hacer `{% url 'tournament:results' %}` en los templates sin ambigüedad si dos apps tienen una URL con el mismo nombre.

### Vistas basadas en funciones (FBV)

En este proyecto se usan FBV en lugar de Class-Based Views (CBV) por legibilidad:

```python
@login_required          # Decorador: redirige al login si no está autenticado
def grupos(request: HttpRequest) -> HttpResponse:
    groups_data = calcular_clasificaciones()
    return render(request, "tournament/grupos.html", {"groups_data": groups_data})
```

El decorador `@login_required` comprueba `request.user.is_authenticated` antes de ejecutar la vista. Si no está autenticado, redirige a `LOGIN_URL` (definido en settings).

---

## 9. Templates y Tailwind CSS

### Sistema de templates de Django

Los templates usan la sintaxis de Django Template Language (DTL):

```html
{# Comentario #}
{% extends "base.html" %}           {# Herencia: usa base.html como layout #}
{% load i18n %}                     {# Carga la librería de traducción #}

{% block content %}                 {# Sobreescribe este bloque del padre #}
  {% for group in groups_data %}    {# Bucle #}
    {% if group.standings %}        {# Condicional #}
      {{ group.letter }}            {# Variable #}
    {% endif %}
  {% endfor %}
{% endblock %}
```

### Herencia de templates (`base.html`)

`base.html` define el layout completo (navbar, footer, scripts) con `{% block %}` que las páginas hijas pueden rellenar:

```html
<!-- base.html -->
<nav>...</nav>
<main>
  {% block content %}{% endblock %}   {# Cada página pone su contenido aquí #}
</main>
<footer>...</footer>
```

```html
<!-- grupos.html -->
{% extends "base.html" %}
{% block content %}
  <h1>Clasificaciones</h1>
{% endblock %}
```

### Tailwind CSS v4 desde CDN

En lugar de instalar Tailwind como dependencia de Node.js y tener un proceso de build, usamos el CDN de Tailwind v4:

```html
<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
```

Tailwind v4 con el CDN browser analiza las clases en el HTML al cargar la página y genera el CSS al vuelo. Perfecto para proyectos sin build step de frontend.

**Desventaja:** en producción con muchos usuarios sería más eficiente tener el CSS precompilado. Para este proyecto el tradeoff merece la pena.

### Alpine.js

[Alpine.js](https://alpinejs.dev/) es un framework de JavaScript mínimo para añadir interactividad declarativa al HTML:

```html
<div x-data="{ open: false }">
  <button @click="open = !open">Toggle</button>
  <div x-show="open">Contenido visible/oculto</div>
</div>
```

No necesita build step ni `npm install`. Se carga desde CDN. Ideal para casos simples como tabs, dropdowns y confirmaciones.

---

## 10. Archivos estáticos y WhiteNoise

Los archivos estáticos (CSS, JS, imágenes) necesitan un tratamiento especial en producción.

**En desarrollo:** Django los sirve directamente (lento pero suficiente).

**En producción:** un servidor web como Nginx los sirve mucho más eficientemente que Python.

**WhiteNoise** es un middleware de Django que permite servir archivos estáticos directamente desde Django de forma eficiente en producción, sin necesitar Nginx. Es la solución más simple para apps pequeñas.

```python
# base.py
MIDDLEWARE = [
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Justo después de SecurityMiddleware
    ...
]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
```

`CompressedManifestStaticFilesStorage` comprime los ficheros (gzip/brotli) y añade un hash al nombre (`main.abc123.css`) para evitar problemas de caché en los navegadores.

```bash
# Genera staticfiles/ con todos los archivos comprimidos y con hash
python manage.py collectstatic
```

---

## 11. Internacionalización (i18n)

### ¿Cómo funciona?

1. En el código Python y templates, se envuelven los textos con funciones de traducción:

```python
# Python
from django.utils.translation import gettext_lazy as _
verbose_name = _("Selección nacional")

# Template
{% load i18n %}
{% trans "Clasificaciones" %}
```

2. Django extrae todos los textos marcados a un fichero `.po`:

```bash
cd backend
uv run django-admin makemessages --locale eu
```

3. Se traduce el `.po` rellenando los `msgstr`:

```
msgid "Clasificaciones"       ← texto original (fuente)
msgstr "Sailkapen-taulak"     ← traducción al euskera
```

4. Se compila el `.po` a un fichero binario `.mo` (que Django lee):

```bash
uv run django-admin compilemessages --locale eu
```

### El error clásico: textos en el idioma equivocado

El `msgid` **siempre debe estar en el idioma base** del proyecto (castellano en este caso). Si pones el texto directamente en euskera en el template sin `{% trans %}`, o si el `msgid` está en euskera, el sistema de traducción no funciona.

```html
<!-- ❌ INCORRECTO: texto hardcodeado, siempre en euskera -->
<h1>Sailkapen-taulak</h1>

<!-- ❌ INCORRECTO: msgid en euskera, no se puede traducir al castellano -->
{% trans "Sailkapen-taulak" %}

<!-- ✅ CORRECTO: msgid en castellano, .po lo traduce a euskera -->
{% trans "Clasificaciones" %}
```

### `LocaleMiddleware`

El middleware `django.middleware.locale.LocaleMiddleware` detecta el idioma del usuario (de la sesión o del header `Accept-Language`) y activa la traducción correcta automáticamente.

---

## 12. Signals de Django

Los signals permiten que partes del código reaccionen a eventos sin acoplarse directamente:

```python
# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Match

@receiver(post_save, sender=Match)
def propagate_match_winner(sender, instance: Match, **kwargs) -> None:
    """Cuando un partido se guarda, propaga el ganador al siguiente partido del bracket."""
    if not instance.is_finished:
        return
    # ... lógica de propagación
```

**Por qué signals en lugar de lógica en la vista:**
La propagación del ganador ocurre siempre que un `Match` se guarda como finalizado, sin importar desde dónde (admin de Django, vista de gestión, API, comando de manage). Si estuviera en la vista, solo funcionaría desde esa vista.

**Dónde se registran:** en `apps.py` de la app:

```python
# tournament/apps.py
class TournamentConfig(AppConfig):
    def ready(self):
        import apps.tournament.signals  # noqa: F401
```

---

## 13. Management commands

Los management commands son scripts Python que se ejecutan con `python manage.py <nombre>`. Django incluye muchos (`migrate`, `createsuperuser`, `collectstatic`) y puedes crear los tuyos.

```
apps/tournament/management/
└── commands/
    ├── load_teams.py        → carga equipos desde data/teams.json
    ├── load_fixtures.py     → carga los 104 partidos desde data/fixtures.json
    └── setup_bracket.py    → configura las relaciones next_match del bracket
```

**Estructura mínima:**

```python
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Descripción del comando"

    def handle(self, *args, **options):
        # Aquí va la lógica
        self.stdout.write(self.style.SUCCESS("¡Hecho!"))
```

**Por qué management commands en lugar de un script Python normal:**
Tienen acceso completo al entorno Django (modelos, settings, BD) sin configuración extra. Se pueden ejecutar desde Docker (`make load-fixtures`) o desde el servidor.

---

## 14. Docker y Docker Compose

### ¿Por qué Docker?

Sin Docker, cada desarrollador tiene que instalar PostgreSQL en su máquina con la versión correcta, con el usuario correcto, etc. Con Docker, el entorno es idéntico para todos y no contamina el sistema.

### Multi-stage build en el Dockerfile

```dockerfile
# Etapa 1: builder — instala dependencias
FROM python:3.13-slim AS builder
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev    # Solo dependencias de producción

# Etapa 2: runtime — imagen final ligera
FROM python:3.13-slim AS runtime
# Usuario no-root por seguridad
RUN addgroup --system django && adduser --system --ingroup django django
# Solo copia el .venv del builder, no las herramientas de build
COPY --from=builder /app/.venv /app/.venv
COPY backend/ .
USER django
CMD ["gunicorn", ...]
```

**Por qué multi-stage:** la etapa builder necesita herramientas de compilación que no deben estar en producción (ocupan espacio y son superficie de ataque). La imagen final solo contiene lo imprescindible.

### Docker Compose

`docker-compose.yml` orquesta múltiples contenedores:

```yaml
services:
  db:                              # PostgreSQL
    image: postgres:16-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data   # Datos persistentes

  backend:                         # Django
    build: ...
    volumes:
      - ../backend:/app            # El código local se monta en el contenedor
      - backend_venv:/app/.venv    # El venv NO se sobreescribe con el mount
    depends_on:
      db:
        condition: service_healthy # Espera a que PostgreSQL esté listo
```

**El truco del volumen del venv:** si montamos `../backend:/app`, el directorio `.venv/` local también se montaría, pero en el contenedor las rutas son diferentes. Por eso usamos un volumen nombrado `backend_venv:/app/.venv` que "tapa" el `.venv` local con el del contenedor.

### Variables de entorno en Docker Compose

```yaml
environment:
  DB_PASSWORD: ${DB_PASSWORD:?Variable DB_PASSWORD requerida}
```

`${VAR:?mensaje}` → si `VAR` no está definida, Docker falla con ese mensaje. Es una validación explícita que evita arrancar con configuración incompleta.

---

## 15. El Makefile

Un `Makefile` es un archivo de recetas que abrevian comandos largos:

```makefile
COMPOSE := docker compose -f docker/docker-compose.yml
ENV_FILE := backend/.env

up-d:
    $(COMPOSE) --env-file $(ENV_FILE) up -d

migrate:
    $(COMPOSE) --env-file $(ENV_FILE) exec backend python manage.py migrate
```

```bash
# En lugar de escribir esto cada vez:
docker compose -f docker/docker-compose.yml --env-file backend/.env exec backend python manage.py migrate

# Solo escribes:
make migrate
```

Los targets con `.PHONY` le dicen a `make` que ese nombre no es un fichero sino un comando:

```makefile
.PHONY: up up-d down migrate test
```

---

## 16. Ruff: linter y formatter

[Ruff](https://docs.astral.sh/ruff/) es una herramienta que reemplaza a cinco herramientas clásicas de Python: `flake8` (linting), `black` (formateo), `isort` (ordenar imports), `pyupgrade` (modernizar sintaxis) y `bandit` (seguridad).

```bash
# Comprueba el código sin modificarlo
uv run ruff check .

# Auto-corrige lo que puede
uv run ruff check --fix .

# Formatea el código (equivale a black)
uv run ruff format .
```

### Configuración en `pyproject.toml`

```toml
[tool.ruff.lint]
select = [
    "E",   # pycodestyle — estilo PEP 8
    "F",   # pyflakes — variables no usadas, imports no usados
    "I",   # isort — orden de imports
    "B",   # bugbear — patrones problemáticos
    "DJ",  # flake8-django — errores específicos de Django
    "UP",  # pyupgrade — usa sintaxis moderna de Python
]
ignore = ["E501"]  # No limitamos la longitud de línea (lo hace el formatter)
```

**Por qué un linter:**
El linter detecta errores antes de ejecutar el código. Por ejemplo, `F401` avisa de imports no usados, `B006` avisa de argumentos mutables por defecto (un error clásico de Python).

---

## 17. Pre-commit hooks

Los hooks de pre-commit son scripts que se ejecutan **automáticamente antes de cada `git commit`**. Si fallan, el commit no se realiza.

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks:
      - id: trailing-whitespace       # No espacios al final de línea
      - id: end-of-file-fixer         # Siempre newline al final
      - id: no-commit-to-branch       # Prohibe commits directos a main/develop
        args: ["--branch", "main", "--branch", "develop"]

  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks:
      - id: ruff                      # Linting con auto-fix
      - id: ruff-format               # Formateo
```

### Instalación (una sola vez por desarrollador)

```bash
cd backend
uv run pre-commit install
```

Esto instala el hook en `.git/hooks/pre-commit`. A partir de ahí, se ejecuta solo en cada commit.

**El hook `no-commit-to-branch`** es especialmente útil: obliga a trabajar en ramas de feature, nunca directamente en `main` o `develop`. Esto fuerza el flujo de trabajo con pull requests.

---

## 18. Tests con pytest-django

### ¿Por qué pytest en lugar de `unittest`?

`pytest` tiene una sintaxis más limpia (no necesitas clases), fixtures más potentes y un ecosistema de plugins enorme. `pytest-django` añade la integración con Django (gestión de la BD de test, cliente HTTP, etc.).

### Anatomía de un test

```python
import pytest
from django.urls import reverse

@pytest.mark.django_db          # Este test necesita acceso a la BD
class TestGruposView:
    def test_accesible_sin_autenticar(self, client):
        resp = client.get(reverse("tournament:grupos"))  # URL por nombre
        assert resp.status_code == 200
```

### Fixtures de pytest

Las fixtures son funciones que preparan datos o recursos para los tests:

```python
@pytest.fixture
def group_teams(db):
    """Crea 4 equipos en el grupo A."""
    return [
        NationalTeam.objects.create(name=f"Equipo {i}", group="A", ...)
        for i in range(4)
    ]

def test_clasificacion(client, group_teams):  # group_teams se inyecta automáticamente
    resp = client.get(reverse("tournament:grupos"))
    assert len(resp.context["groups_data"]) == 1
```

**Cómo funciona la BD en los tests:**
Cada test se ejecuta dentro de una transacción que se revierte al final. La BD queda limpia para el siguiente test, sin necesidad de `teardown` manual.

### `conftest.py`

Fichero especial que pytest busca automáticamente. Las fixtures definidas aquí están disponibles en todos los tests del directorio y subdirectorios. El `conftest.py` raíz de `backend/` define fixtures compartidas por todas las apps.

### Settings de test (`config/settings/test.py`)

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",        # Base de datos en RAM, no en disco
    }
}
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",  # Más rápido que bcrypt
]
```

SQLite en memoria es mucho más rápido que PostgreSQL para tests porque no necesita red ni disco. Los tests corren en segundos.

---

## 19. Cobertura de código

La cobertura mide qué porcentaje de tu código es ejecutado por los tests. No garantiza que los tests sean buenos, pero garantiza que al menos el código se ejecuta.

```toml
[tool.coverage.report]
fail_under = 60   # pytest falla si la cobertura baja del 60%
show_missing = true   # Muestra qué líneas no están cubiertas
```

```bash
uv run pytest  # Genera el informe de cobertura automáticamente
```

**Salida típica:**
```
apps/tournament/views.py    185    67    64%   25-46, 283, 286
```

Significa: 185 líneas totales, 67 no ejecutadas por tests, 64% de cobertura. Las líneas 25-46, 283 y 286 no están cubiertas.

**Por qué el umbral no es 100%:**
El 100% es difícil de alcanzar y no siempre aporta valor. Las migraciones, el código de administración y los casos de error rarísimos tienen poco ROI en tests. El 60% es un umbral razonable para empezar que garantiza que lo más importante está testado.

---

## 20. GitHub Actions — CI/CD

**CI (Continuous Integration):** cada vez que alguien sube código, se ejecutan automáticamente los tests y el linter.

**CD (Continuous Deployment):** cuando los tests pasan, el código se despliega automáticamente al servidor.

### El workflow `.github/workflows/ci.yml`

```yaml
on:
  push:
    branches: [main, develop]   # Se activa al hacer push a estas ramas
  pull_request:
    branches: [main, develop]   # Y cuando se abre un PR hacia ellas
```

**Pasos del CI:**

1. `checkout` — descarga el código del commit
2. `setup-uv` — instala uv con caché (para no descargar siempre todo)
3. `uv sync --all-groups` — instala dependencias de prod y dev
4. `ruff check` — lint
5. `ruff format --check` — verifica formateo sin modificar
6. `mypy` — tipado estático (no bloquea porque está en progreso)
7. `pytest` — tests + cobertura

**Si algún paso falla,** GitHub marca el commit con ❌ y lo notifica. No se puede hacer merge de un PR con el CI en rojo.

### Secretos en GitHub Actions

Las variables de entorno sensibles se configuran en `Settings → Secrets and variables → Actions` del repositorio de GitHub. En el workflow se accede así:

```yaml
env:
  SECRET_KEY: ${{ secrets.SECRET_KEY }}
  DB_PASSWORD: ${{ secrets.DB_PASSWORD }}
```

---

## 21. Flujo de trabajo con Git

El proyecto usa una variante de **Git Flow**:

```
main          → código en producción (solo merges desde develop)
develop       → integración (base de trabajo diario)
feature/*     → nuevas funcionalidades
fix/*         → correcciones de bugs
```

### Flujo de una nueva funcionalidad

```bash
# 1. Partir siempre desde develop actualizado
git checkout develop
git pull origin develop

# 2. Crear rama de feature
git checkout -b feature/mi-nueva-funcionalidad

# 3. Trabajar, hacer commits...
git add -A
git commit -m "feat(tournament): añadir vista de grupos"
# ↑ El hook pre-commit se ejecuta aquí automáticamente

# 4. Merge sin fast-forward (crea un commit de merge explícito)
git checkout develop
git merge --no-ff feature/mi-nueva-funcionalidad -m "Merge feature/..."

# 5. Subir
git push origin develop
```

**`--no-ff` (no fast-forward):**
Sin esta opción, si la rama de feature tiene commits lineales sobre develop, Git los "aplana" y es como si se hubieran hecho directamente en develop. Con `--no-ff` siempre hay un commit de merge, lo que hace el historial más legible.

### Mensajes de commit (Conventional Commits)

```
feat(tournament): añadir vista de grupos
fix(bracket): corregir error NOT NULL en reset
docs: actualizar LEARNING.md
test(pool): añadir tests del motor de puntuación
refactor(views): extraer lógica de clasificación
```

Formato: `tipo(scope): descripción`. Esto permite generar changelogs automáticos y entender el historial de un vistazo.

---

## 22. Flujo completo de una petición HTTP

Cuando el navegador carga `/grupos/`:

```
1. Nginx (si hay) recibe la petición y la pasa a Gunicorn

2. Gunicorn (servidor WSGI) la entrega al código Django

3. Django ejecuta los MIDDLEWARE en orden:
   - SecurityMiddleware: cabeceras de seguridad
   - WhiteNoiseMiddleware: ¿es un archivo estático? Si sí, lo sirve y para
   - SessionMiddleware: carga la sesión del usuario
   - LocaleMiddleware: detecta el idioma y activa las traducciones
   - CsrfViewMiddleware: valida el token CSRF en POST
   - AuthenticationMiddleware: pone request.user disponible
   ...

4. Django busca en config/urls.py → apps/tournament/urls.py
   Encuentra: path("grupos/", views.grupos, name="grupos")

5. Ejecuta views.grupos(request):
   - Consulta NationalTeam.objects a la BD
   - Calcula clasificaciones
   - Llama a render(request, "tournament/grupos.html", context)

6. Django Template Engine:
   - Busca "tournament/grupos.html" en BASE_DIR/templates/
   - Lo procesa: sustituye {% trans %}, {{ variables }}, {% for %}...
   - Los {% trans %} consultan el fichero .mo del idioma activo

7. Devuelve un HttpResponse con el HTML generado

8. Django ejecuta los MIDDLEWARE en orden inverso (response)

9. Gunicorn envía la respuesta HTTP al navegador

10. El navegador descarga el HTML, luego los scripts (Tailwind CDN,
    Alpine.js CDN) y renderiza la página
```

---

## 23. Errores comunes y por qué ocurren

### `MultipleObjectsReturned`

```python
# ❌ Si hay más de un registro que cumple la condición, falla
Match.objects.get(scheduled_at=..., phase="GRP")

# ✅ Usa filter() cuando puede haber más de uno
Match.objects.filter(scheduled_at=..., phase="GRP").first()
```

### `NOT NULL constraint` en un CharField

```python
# El modelo tiene: next_match_slot = models.CharField(default="")
# ❌ None viola el NOT NULL de PostgreSQL
Match.objects.update(next_match_slot=None)

# ✅ Usa la cadena vacía para "sin valor"
Match.objects.update(next_match_slot="")
```

### `distinct()` con `ordering` en el modelo

```python
# NationalTeam tiene ordering = ["group", "name"]
# ❌ Django añade "name" a la query → distinct() no deduplica por "group" solo
NationalTeam.objects.values_list("group", flat=True).distinct()

# ✅ Sobreescribe el ordering explícitamente
NationalTeam.objects.order_by("group").values_list("group", flat=True).distinct()
```

### Ruta de fichero diferente en Docker

```python
# ❌ Puede funcionar local pero falla en Docker (rutas diferentes)
Path(__file__).resolve().parents[5] / "data" / "fixtures.json"

# ✅ Usa BASE_DIR que siempre apunta al directorio backend/
from django.conf import settings
Path(settings.BASE_DIR) / "data" / "fixtures.json"
```

---

## 24. Herramientas que deberías conocer

| Herramienta | Para qué | Por qué importa |
|---|---|---|
| **uv** | Gestión de entornos y paquetes Python | El futuro del ecosistema Python, 100x más rápido que pip |
| **ruff** | Linting y formateo | Reemplaza flake8 + black + isort en una sola herramienta |
| **pytest** | Tests | El estándar de facto en Python moderno |
| **pre-commit** | Automatizar checks antes de commit | Garantiza que el código subido siempre pasa el linter |
| **Docker** | Entornos reproducibles | "Funciona en mi máquina" eliminado |
| **GitHub Actions** | CI/CD automatizado | Tests automáticos en cada push |
| **python-decouple** | Variables de entorno | Nunca secretos hardcodeados en el código |
| **WhiteNoise** | Servir estáticos sin Nginx | Simplifica el despliegue |
| **psycopg2** | Conectar Python a PostgreSQL | El driver más usado y probado |
| **Tailwind CSS** | Estilos utilitarios | CSS sin escribir CSS, diseño directamente en HTML |
| **Alpine.js** | Interactividad mínima | JavaScript sin build step |

### Recursos para seguir aprendiendo

- [Django docs](https://docs.djangoproject.com/) — la mejor documentación de cualquier framework web
- [Two Scoops of Django](https://www.feldroy.com/books/two-scoops-of-django-3-x) — libro de buenas prácticas
- [uv docs](https://docs.astral.sh/uv/) — guía completa del gestor de paquetes
- [ruff docs](https://docs.astral.sh/ruff/) — todas las reglas disponibles
- [pytest docs](https://docs.pytest.org/) — fixtures avanzadas, parametrize, markers
- [Twelve-Factor App](https://12factor.net/es/) — metodología de apps modernas (explica por qué .env, por qué separar configuración de código, etc.)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/) — los 10 errores de seguridad más comunes en aplicaciones web
- [Conventional Commits](https://www.conventionalcommits.org/) — estándar de mensajes de commit

---

*Este documento describe el estado del proyecto a 20 de mayo de 2026. Actualízalo cuando añadas nuevas tecnologías o cambies patrones arquitectónicos.*

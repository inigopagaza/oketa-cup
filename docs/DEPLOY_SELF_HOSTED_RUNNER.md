# Deploy Automático Con Self-Hosted Runner

Guía paso a paso para sustituir el deploy por SSH desde GitHub Actions por un runner self-hosted ejecutándose dentro de tu propia máquina de deploy.

Objetivo:

- Que GitHub Actions no tenga que entrar por SSH a tu LXC.
- Que el propio servidor se conecte saliendo a GitHub, recoja jobs y ejecute localmente el deploy.
- Automatizar dos casos distintos:
  - deploy de código cuando hay cambios en `main`
  - refresco de datos de partidos cuando cambia `backend/data/fixtures.json`

Esto encaja mejor con tu caso porque el problema actual está en la conectividad SSH desde GitHub hacia tu red/casa/LXC.

## 1. Idea general

Con un self-hosted runner, el flujo cambia de esto:

```text
GitHub Actions -> SSH -> servidor
```

a esto:

```text
servidor -> GitHub Actions -> ejecuta job localmente en el servidor
```

Ventajas:

- No necesitas abrir SSH al exterior para Actions.
- No dependes de NAT, CGNAT, IP pública o reglas raras del router.
- Puedes ejecutar directamente `git`, `docker compose` y comandos Django dentro del propio servidor.
- Separas mejor el deploy de código y el refresh de datos.

Riesgo importante:

- Un self-hosted runner en producción tiene mucho poder. Cualquier workflow que corra ahí puede ejecutar comandos en la máquina. Por eso conviene usarlo solo para tu repo y solo para deploy.

## 2. Arquitectura recomendada

Recomendación para tu caso:

- Instalar el runner en el mismo LXC donde ya vive `/home/deploy/oketa-cup`.
- Ejecutarlo como usuario `deploy`.
- Mantener el repo desplegado en `/home/deploy/oketa-cup`.
- Usar una etiqueta dedicada, por ejemplo `oketa-prod`.
- Dejar el runner fuera del repo, por ejemplo en `/opt/actions-runner/oketa-prod`.

Esquema:

```text
GitHub
  -> workflow deploy-code
  -> workflow deploy-fixtures

LXC oketa-cup
  /opt/actions-runner/oketa-prod     <- runner
  /home/deploy/oketa-cup             <- repo desplegado
  docker compose                     <- servicios productivos
```

## 3. Requisitos previos

Antes de empezar, asegúrate de que en el LXC ya tienes:

- usuario `deploy`
- `git`
- `curl`
- `tar`
- `docker`
- `docker compose`
- acceso de `deploy` al grupo `docker`
- repo ya clonado en `/home/deploy/oketa-cup`

Compruébalo con:

```bash
su - deploy

whoami
docker --version
docker compose version
git --version
groups
ls -la /home/deploy/oketa-cup
```

Si falta algo:

```bash
apt update
apt install -y curl git tar
usermod -aG docker deploy
```

Después de añadir `deploy` al grupo `docker`, cierra sesión y vuelve a entrar.

## 4. Preparar el directorio del runner

En el LXC, como `root` o con `sudo`:

```bash
mkdir -p /opt/actions-runner/oketa-prod
chown -R deploy:deploy /opt/actions-runner/oketa-prod
```

Ahora entra como `deploy`:

```bash
su - deploy
cd /opt/actions-runner/oketa-prod
```

## 5. Dar de alta el runner en GitHub

En GitHub:

1. Entra en tu repo.
2. Ve a `Settings`.
3. Ve a `Actions`.
4. Ve a `Runners`.
5. Pulsa `New self-hosted runner`.
6. Elige:
   - sistema: Linux
   - arquitectura: x64

GitHub te mostrará unos comandos parecidos a estos. Ejecútalos en el LXC como `deploy`.

```bash
cd /opt/actions-runner/oketa-prod

curl -o actions-runner-linux-x64.tar.gz -L https://github.com/actions/runner/releases/download/vX.Y.Z/actions-runner-linux-x64-X.Y.Z.tar.gz
tar xzf ./actions-runner-linux-x64.tar.gz
```

Luego configura el runner con el comando que te dará GitHub. Será parecido a esto:

```bash
./config.sh --url https://github.com/inigopagaza/oketa-cup --token TU_TOKEN_TEMPORAL
```

Cuando pregunte:

- `Enter the name of the runner`: `oketa-prod-runner`
- `Enter any additional labels`: `oketa-prod`
- `Enter name of work folder`: deja `_work`

Importante:

- Ese token de alta expira rápido. Copia y pega el comando en ese momento.
- No es un secreto permanente como una clave SSH; solo sirve para registrar el runner.

## 6. Instalarlo como servicio systemd

Todavía como `deploy`, dentro de `/opt/actions-runner/oketa-prod`:

```bash
sudo ./svc.sh install deploy
sudo ./svc.sh start
```

Comprueba el estado:

```bash
sudo ./svc.sh status
sudo systemctl status actions.runner.* --no-pager
```

Y en GitHub deberías ver el runner como `Idle`.

## 7. Verificaciones mínimas del runner

Haz estas pruebas en el LXC:

```bash
su - deploy

cd /home/deploy/oketa-cup
git status

docker compose -f docker/docker-compose.prod.yml --env-file .env ps
```

Si esto falla, no sigas con la automatización todavía.

Los dos problemas más comunes son:

- el runner arranca pero el usuario no tiene permisos Docker
- el repo desplegado no pertenece a `deploy`

Si hay problemas de permisos:

```bash
sudo chown -R deploy:deploy /home/deploy/oketa-cup
sudo usermod -aG docker deploy
```

## 8. Qué cambia respecto al deploy por SSH

Con este modelo:

- ya no necesitas `DEPLOY_HOST`
- ya no necesitas `DEPLOY_USER`
- ya no necesitas `DEPLOY_KEY`
- ya no necesitas `appleboy/ssh-action`

Tu workflow de deploy debe ejecutarse con:

```yaml
runs-on: [self-hosted, linux, x64, oketa-prod]
```

y luego lanzar comandos locales con `run:`.

## 8.1 Detalle importante de este repo: `fixtures.json` va dentro de la imagen

En el estado actual del proyecto:

- la imagen Docker copia `backend/` completo dentro de `/app`
- eso incluye `backend/data/fixtures.json`
- `load_fixtures` intenta leer primero `/app/data/fixtures.json`
- `/data/fixtures.json` solo se usa como fallback

Conclusión:

- un cambio en `backend/data/fixtures.json` no debe tratarse como un simple `git pull`
- antes de ejecutar `load_fixtures --clear`, hay que asegurarse de que el contenedor `web` ya usa la imagen nueva

En la práctica, el workflow de refresh de datos debe hacer al menos:

```bash
docker compose -f docker/docker-compose.prod.yml --env-file .env pull web
docker compose -f docker/docker-compose.prod.yml --env-file .env up -d web nginx
```

## 8.2 Detalle importante de CI/CD: evita carreras entre build y deploy

Ahora mismo tu repo tiene el build de imagen en [ci.yml](../.github/workflows/ci.yml).

Si disparas el deploy directamente con `push` a `main` en otro workflow distinto, existe el riesgo de que el deploy intente hacer `docker compose pull` antes de que GHCR tenga publicada la imagen nueva.

La solución recomendada es:

- disparar el deploy con `workflow_run` cuando termine correctamente `CI` sobre `main`

Así el deploy ocurre después del build y del push de imagen, no en paralelo.

## 9. Recomendación de workflows

Separa el deploy en dos workflows.

### 9.1 Deploy de código

Este workflow debe dispararse cuando termine correctamente `CI` en `main`.

Archivo recomendado:

`.github/workflows/deploy-code.yml`

```yaml
name: Deploy code to production

on:
  workflow_run:
    workflows: ["CI"]
    types: [completed]

concurrency:
  group: production-deploy
  cancel-in-progress: false

jobs:
  deploy-code:
    if: ${{ github.event.workflow_run.conclusion == 'success' && github.event.workflow_run.head_branch == 'main' }}
    runs-on: [self-hosted, linux, x64, oketa-prod]

    steps:
      - name: Update deployed repo
        run: |
          set -euo pipefail
          cd /home/deploy/oketa-cup
          git fetch origin main
          git checkout main
          git merge --ff-only origin/main

      - name: Pull containers and deploy
        run: |
          set -euo pipefail
          cd /home/deploy/oketa-cup
          docker compose -f docker/docker-compose.prod.yml --env-file .env pull
          docker compose -f docker/docker-compose.prod.yml --env-file .env run --rm --no-deps web python manage.py migrate --noinput
          docker compose -f docker/docker-compose.prod.yml --env-file .env up -d --force-recreate --remove-orphans

      - name: Quick status
        run: |
          cd /home/deploy/oketa-cup
          docker compose -f docker/docker-compose.prod.yml --env-file .env ps
```

Notas:

- Uso `git merge --ff-only origin/main` para evitar merges raros en el servidor.
- Uso `run --rm --no-deps web` porque en LXC a veces es más robusto que `exec` para management commands.
- Al dispararse por `workflow_run`, el deploy espera a que la imagen nueva ya exista en GHCR.

### 9.2 Refresh automático de partidos y datos del calendario

Este workflow sirve para refrescar partidos cuando cambia `backend/data/fixtures.json` o cuando quieres reejecutar la carga manualmente.

Importante: como los fixtures actuales van dentro de la imagen, este workflow también debe hacer `pull web` antes de recargar datos.

Archivo recomendado:

`.github/workflows/deploy-fixtures.yml`

```yaml
name: Refresh production fixtures

on:
  push:
    branches: [main]
    paths:
      - 'backend/data/fixtures.json'
  workflow_dispatch:

concurrency:
  group: production-data-refresh
  cancel-in-progress: false

jobs:
  refresh-fixtures:
    runs-on: [self-hosted, linux, x64, oketa-prod]

    steps:
      - name: Update deployed repo
        run: |
          set -euo pipefail
          cd /home/deploy/oketa-cup
          git fetch origin main
          git checkout main
          git merge --ff-only origin/main

      - name: Ensure services are up
        run: |
          set -euo pipefail
          cd /home/deploy/oketa-cup
          docker compose -f docker/docker-compose.prod.yml --env-file .env pull web
          docker compose -f docker/docker-compose.prod.yml --env-file .env up -d web nginx

      - name: Reload fixtures and rebuild bracket
        run: |
          set -euo pipefail
          cd /home/deploy/oketa-cup
          docker compose -f docker/docker-compose.prod.yml --env-file .env run --rm --no-deps web python manage.py load_fixtures --clear
          docker compose -f docker/docker-compose.prod.yml --env-file .env run --rm --no-deps web python manage.py setup_bracket
```

Este workflow sirve para tu caso de:

- cambio de horario de partidos
- cambio de venue
- refresh de `fixtures.json`

Si más adelante quieres independizar completamente el refresh de datos respecto a la imagen, entonces te interesará cambiar `load_fixtures` para que priorice `/data/fixtures.json`.

### 9.3 Si quieres automatizar también cambios de selecciones u otros datos base

Si en el futuro quieres que también se automaticen cambios sobre `teams.json`, añade otro workflow separado, por ejemplo:

- trigger por cambios en `backend/data/teams.json`
- ejecutar:

```bash
python manage.py load_teams
python manage.py load_fixtures --clear
python manage.py setup_bracket
```

Mi recomendación es mantenerlo separado de `fixtures.json`, porque así no recargas selecciones cuando solo cambian horarios.

## 10. Qué hacer con tu workflow actual por SSH

Tu workflow actual es [deploy.yml](../.github/workflows/deploy.yml) y sigue usando `appleboy/ssh-action`.

Cuando migres a self-hosted runner, haz una de estas dos cosas:

1. Borrarlo.
2. Renombrarlo a algo como `deploy_ssh_old.yml.disabled` fuera de `.github/workflows`.

No dejes las dos estrategias activas a la vez, porque podrías disparar deploy doble.

## 11. Secretos y credenciales que sí pueden seguir siendo necesarios

Aunque elimines SSH para Actions, todavía puede hacerte falta alguna credencial en el servidor:

- Si el repo es público: normalmente no necesitas nada especial para `git fetch origin main`.
- Si el repo es privado: configura una deploy key de solo lectura o un token para que el servidor pueda hacer `git fetch`.
- Si la imagen de GHCR es privada: haz `docker login ghcr.io` en el servidor con un token de lectura de paquetes.

Ejemplo de login en el servidor si GHCR fuera privado:

```bash
echo 'TU_TOKEN' | docker login ghcr.io -u TU_USUARIO_GITHUB --password-stdin
```

## 12. Logs y diagnóstico

Si algo falla, mira estos puntos en este orden.

Estado del runner:

```bash
sudo systemctl status actions.runner.* --no-pager
journalctl -u $(systemctl list-units --type=service --all | awk '/actions.runner/ {print $1; exit}') -n 200 --no-pager
```

Estado del repo desplegado:

```bash
su - deploy
cd /home/deploy/oketa-cup
git status
git log --oneline -n 5
```

Estado de contenedores:

```bash
cd /home/deploy/oketa-cup
docker compose -f docker/docker-compose.prod.yml --env-file .env ps
docker compose -f docker/docker-compose.prod.yml --env-file .env logs --tail=100 web
docker compose -f docker/docker-compose.prod.yml --env-file .env logs --tail=100 nginx
```

## 13. Checklist de implantación

Marca esto en orden:

- [ ] El usuario `deploy` existe y tiene acceso a Docker.
- [ ] El repo desplegado está en `/home/deploy/oketa-cup`.
- [ ] El runner está instalado en `/opt/actions-runner/oketa-prod`.
- [ ] El runner aparece `Idle` en GitHub.
- [ ] El workflow viejo por SSH está desactivado.
- [ ] Existe un workflow `deploy-code.yml` con `runs-on: [self-hosted, linux, x64, oketa-prod]`.
- [ ] Existe un workflow `deploy-fixtures.yml` con trigger por cambios en `backend/data/fixtures.json`.
- [ ] Un push a `main` despliega código correctamente.
- [ ] Un cambio en `backend/data/fixtures.json` refresca partidos en producción.

## 14. Recomendación final para tu repo

Para tu caso concreto, la opción más sólida es esta:

- CI sigue en GitHub-hosted (`ubuntu-latest`).
- Deploy a producción cambia a self-hosted runner en el LXC.
- Deploy de código se dispara con `workflow_run` cuando termina bien `CI` en `main`.
- El refresh de datos se deja en workflow separado para recargar `fixtures.json` cuando haga falta.
- `main` se protege con PR obligatorio y checks de CI verdes.

Así consigues:

- CI limpia y barata en GitHub
- CD local sin SSH entrante
- automatización completa de código y de cambios de calendario

## 15. Si quieres dejarlo fino del todo

Como siguiente mejora, lo ideal es mover la lógica repetida de deploy a scripts versionados, por ejemplo:

- `scripts/deploy_code.sh`
- `scripts/refresh_fixtures.sh`

Entonces los workflows solo llaman a esos scripts y el comportamiento queda más fácil de depurar y reutilizar también manualmente en servidor.

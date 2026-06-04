# Deploy rapido (comandos copy/paste)

Guia corta para desplegar cambios en produccion desde el servidor.

## Atajo desde tu Mac (1 comando)

Tambien puedes ejecutar el deploy remoto por SSH sin entrar manualmente al servidor.

Opcion recomendada: alias SSH en tu Mac (`~/.ssh/config`):

```sshconfig
Host oketa-prod
  HostName TU_IP_O_HOST
  User deploy
  Port 22
  IdentityFile ~/.ssh/id_ed25519
```

Con eso, puedes lanzar directamente:

```bash
./scripts/deploy-code-ssh.sh
./scripts/deploy-fixtures-ssh.sh
```

Alternativa 1 (variable de entorno, solo una vez por terminal):

```bash
export PROD_SSH_TARGET="deploy@TU_IP_O_HOST"
# opcional si no usas la ruta por defecto
export PROD_APP_DIR="/home/deploy/oketa-cup"
```

Alternativa 2 (pasando destino por argumento):

```bash
./scripts/deploy-code-ssh.sh deploy@TU_IP_O_HOST
./scripts/deploy-fixtures-ssh.sh deploy@TU_IP_O_HOST
```

Si la ruta remota del repo no es la estandar, pasa un segundo argumento:

```bash
./scripts/deploy-code-ssh.sh oketa-prod /home/deploy/oketa-cup
./scripts/deploy-fixtures-ssh.sh oketa-prod /home/deploy/oketa-cup
```

Via `make`:

```bash
make deploy-code-ssh
make deploy-fixtures-ssh
```

## Cuándo usar esto

- Hay cambios en GitHub y quieres aplicarlos en el servidor manualmente.
- Quieres desplegar sin depender de workflows de deploy en GitHub Actions.

## Requisitos

- Tener acceso SSH al servidor (usuario `deploy`).
- Tener el repo en `/home/deploy/oketa-cup`.
- Tener `.env` en la raiz del repo.

## 1) Deploy estandar desde `main` (recomendado)

Ejecuta estos comandos en orden:

```bash
cd /home/deploy/oketa-cup

git checkout main
git pull origin main

docker compose -f docker/docker-compose.prod.yml --env-file .env pull

docker compose -f docker/docker-compose.prod.yml --env-file .env up -d --force-recreate --remove-orphans
```

## 2) Verificacion rapida post-deploy

```bash
docker compose -f docker/docker-compose.prod.yml --env-file .env ps

docker compose -f docker/docker-compose.prod.yml --env-file .env logs --tail=100 web

docker compose -f docker/docker-compose.prod.yml --env-file .env logs --tail=100 nginx
```

## 3) Si hay migraciones pendientes

```bash
docker compose -f docker/docker-compose.prod.yml --env-file .env run --rm --no-deps web python manage.py migrate --noinput

docker compose -f docker/docker-compose.prod.yml --env-file .env up -d --force-recreate web nginx
```

## 3.1) Si cambió `backend/data/fixtures.json`

Aplica esto después del deploy para refrescar horarios/sedes en base de datos:

```bash
docker compose -f docker/docker-compose.prod.yml --env-file .env exec web python manage.py load_fixtures --clear

docker compose -f docker/docker-compose.prod.yml --env-file .env exec web python manage.py setup_bracket
```

Si además cambiaste equipos o querías reconstruir todo desde cero:

```bash
docker compose -f docker/docker-compose.prod.yml --env-file .env exec web python manage.py load_teams

docker compose -f docker/docker-compose.prod.yml --env-file .env exec web python manage.py load_fixtures --clear

docker compose -f docker/docker-compose.prod.yml --env-file .env exec web python manage.py setup_bracket
```

## 4) Si no se ven cambios en frontend/menu

Forzar imagen nueva + recreacion de servicios web:

```bash
cd /home/deploy/oketa-cup

git checkout main
git pull origin main

docker compose -f docker/docker-compose.prod.yml --env-file .env pull web nginx

docker compose -f docker/docker-compose.prod.yml --env-file .env up -d --force-recreate web nginx
```

Comprobacion de que el template nuevo esta en el contenedor:

```bash
docker compose -f docker/docker-compose.prod.yml --env-file .env run --rm --no-deps web sh -lc "grep -n 'menuOpen' /app/templates/base.html"
```

Si eso devuelve lineas, el cambio esta desplegado.

## 5) Deploy puntual desde `develop` (solo validaciones)

Usar solo para pruebas o validacion previa al release:

```bash
cd /home/deploy/oketa-cup

git checkout develop
git pull origin develop

docker compose -f docker/docker-compose.prod.yml --env-file .env pull

docker compose -f docker/docker-compose.prod.yml --env-file .env up -d --force-recreate --remove-orphans
```

## 6) Rollback rapido al commit anterior (emergencia)

```bash
cd /home/deploy/oketa-cup

git checkout main
git log --oneline -n 5
# copia el SHA anterior estable

git checkout <SHA_ESTABLE>

docker compose -f docker/docker-compose.prod.yml --env-file .env up -d --force-recreate --remove-orphans
```

Nota: este rollback deja el repo en modo detached HEAD (temporal). Cuando quieras volver al flujo normal:

```bash
git checkout main
git pull origin main
```

Si quieres dejar el rollback persistente en remoto, hazlo en GitHub con un commit de revert o un PR de rollback.

## 7) Comando unico (todo en uno) para deploy desde `main`

```bash
cd /home/deploy/oketa-cup && \
  git checkout main && \
  git pull origin main && \
  docker compose -f docker/docker-compose.prod.yml --env-file .env pull && \
  docker compose -f docker/docker-compose.prod.yml --env-file .env up -d --force-recreate --remove-orphans && \
  docker compose -f docker/docker-compose.prod.yml --env-file .env ps
```

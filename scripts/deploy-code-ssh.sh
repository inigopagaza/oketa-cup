#!/usr/bin/env bash
set -euo pipefail

# Prioridad: argumento CLI -> variable de entorno -> alias SSH por defecto.
SSH_TARGET="${1:-${PROD_SSH_TARGET:-oketa-prod}}"
APP_DIR="${2:-${PROD_APP_DIR:-/home/deploy/oketa-cup}}"

if [[ -z "$SSH_TARGET" ]]; then
  echo "Error: indica destino SSH (ejemplo: ./scripts/deploy-code-ssh.sh deploy@192.168.1.50)"
  exit 1
fi

echo "[deploy-code] SSH -> $SSH_TARGET"
echo "[deploy-code] App dir -> $APP_DIR"

ssh "$SSH_TARGET" "bash -s -- '$APP_DIR'" <<'EOF'
set -euo pipefail

APP_DIR="$1"
cd "$APP_DIR"

echo "[remote] Update deployed repo"
git fetch origin main
git checkout main
git merge --ff-only origin/main

echo "[remote] Pull containers and deploy"
docker compose -f docker/docker-compose.prod.yml --env-file .env pull
docker compose -f docker/docker-compose.prod.yml --env-file .env run --rm --no-deps -T web python manage.py migrate --noinput < /dev/null
docker compose -f docker/docker-compose.prod.yml --env-file .env down
docker compose -f docker/docker-compose.prod.yml --env-file .env up -d --force-recreate --remove-orphans

echo "[remote] Quick status"
docker compose -f docker/docker-compose.prod.yml --env-file .env ps

echo "[remote] Container timestamps"
for service in web nginx db cloudflared; do
  container_id="$(docker compose -f docker/docker-compose.prod.yml --env-file .env ps -q "$service" || true)"
  if [[ -n "$container_id" ]]; then
    docker inspect --format '  {{.Name}} | created={{.Created}} | status={{.State.Status}} | started={{.State.StartedAt}}' "$container_id"
  fi
done
EOF

echo "[deploy-code] OK"

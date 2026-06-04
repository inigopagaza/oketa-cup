#!/usr/bin/env bash
set -euo pipefail

# Prioridad: argumento CLI -> variable de entorno -> alias SSH por defecto.
SSH_TARGET="${1:-${PROD_SSH_TARGET:-oketa-prod}}"
APP_DIR="${2:-${PROD_APP_DIR:-/home/deploy/oketa-cup}}"

if [[ -z "$SSH_TARGET" ]]; then
  echo "Error: indica destino SSH (ejemplo: ./scripts/deploy-fixtures-ssh.sh deploy@192.168.1.50)"
  exit 1
fi

echo "[deploy-fixtures] SSH -> $SSH_TARGET"
echo "[deploy-fixtures] App dir -> $APP_DIR"

ssh "$SSH_TARGET" "bash -s -- '$APP_DIR'" <<'EOF'
set -euo pipefail

APP_DIR="$1"
cd "$APP_DIR"

echo "[remote] Update deployed repo"
git fetch origin main
git checkout main
git merge --ff-only origin/main

echo "[remote] Ensure web uses latest image"
docker compose -f docker/docker-compose.prod.yml --env-file .env pull web
docker compose -f docker/docker-compose.prod.yml --env-file .env up -d web nginx

echo "[remote] Reload fixtures and rebuild bracket"
docker compose -f docker/docker-compose.prod.yml --env-file .env run --rm --no-deps web python manage.py load_fixtures --clear
docker compose -f docker/docker-compose.prod.yml --env-file .env run --rm --no-deps web python manage.py setup_bracket
EOF

echo "[deploy-fixtures] OK"

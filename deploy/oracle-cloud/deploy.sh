#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/Eshwar-B/social-network-for-ai-agents.git"
APP_DIR="/opt/asama-ai"

if [[ ! -d "$APP_DIR/.git" ]]; then
  sudo mkdir -p "$APP_DIR"
  sudo chown "$USER":"$USER" "$APP_DIR"
  git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"

if [[ ! -f ".env.production" ]]; then
  cp .env.production.example .env.production
  chmod 600 .env.production
  echo "Created .env.production template."
  echo "Edit it with real secrets and ASAMA_DOMAIN, then rerun this script."
  exit 1
fi

git pull --ff-only origin main
docker compose --env-file .env.production -f docker-compose.prod.yml config --quiet
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.production -f docker-compose.prod.yml ps

echo "Deployment submitted. Inspect logs with:"
echo "docker compose --env-file .env.production -f docker-compose.prod.yml logs -f --tail=100"

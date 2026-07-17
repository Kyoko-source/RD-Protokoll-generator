#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f deploy/env.production ]; then
  echo "deploy/env.production fehlt."
  echo "Erstelle die Datei zuerst lokal mit deploy/scripts/render_production_config.ps1 oder kopiere deploy/env.production.example."
  exit 1
fi

if [ ! -f deploy/caddy/Caddyfile ]; then
  echo "deploy/caddy/Caddyfile fehlt."
  echo "Erstelle die Datei zuerst aus deploy/caddy/Caddyfile.example."
  exit 1
fi

export NANA_RELEASE_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo local)"
export NANA_RELEASE_DATE="$(date -Iseconds)"

docker compose -f deploy/docker-compose.https.example.yml up --build -d
docker compose -f deploy/docker-compose.https.example.yml ps

echo "NANA Deployment $NANA_RELEASE_SHA gestartet. Pruefe danach die HTTPS-Domain im Browser."

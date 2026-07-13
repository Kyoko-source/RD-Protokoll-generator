#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/NANA}"
COMPOSE_FILE="${COMPOSE_FILE:-deploy/docker-compose.https.example.yml}"
BACKUP_DIR="${BACKUP_DIR:-/opt/NANA/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"

cd "$APP_DIR"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

timestamp="$(date -u +%Y%m%d-%H%M%S)"
backup_file="$BACKUP_DIR/nana-db-$timestamp.sqlite"
container_id="$(docker compose -f "$COMPOSE_FILE" ps -q nana)"

if [[ -z "$container_id" ]]; then
  echo "NANA container not found. Is docker compose running?" >&2
  exit 1
fi

tmp_file="/tmp/nana-backup-$timestamp.sqlite"

docker compose -f "$COMPOSE_FILE" exec -T nana python - "$tmp_file" <<'PY'
import sqlite3
import sys

target = sys.argv[1]
source = sqlite3.connect("/data/nana.db")
try:
    backup = sqlite3.connect(target)
    try:
        source.backup(backup)
    finally:
        backup.close()
finally:
    source.close()
PY

docker cp "$container_id:$tmp_file" "$backup_file"
docker compose -f "$COMPOSE_FILE" exec -T nana python - "$tmp_file" <<'PY'
import os
import sys

path = sys.argv[1]
if os.path.exists(path):
    os.remove(path)
PY

gzip -f "$backup_file"
sha256sum "$backup_file.gz" > "$backup_file.gz.sha256"

find "$BACKUP_DIR" -type f -name "nana-db-*.sqlite.gz" -mtime +"$KEEP_DAYS" -delete
find "$BACKUP_DIR" -type f -name "nana-db-*.sqlite.gz.sha256" -mtime +"$KEEP_DAYS" -delete

echo "Backup created: $backup_file.gz"

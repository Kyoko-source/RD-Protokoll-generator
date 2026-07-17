#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 /path/to/nana-db.sqlite.gz.enc" >&2
  exit 1
fi

APP_DIR="${APP_DIR:-/opt/NANA}"
COMPOSE_FILE="${COMPOSE_FILE:-deploy/docker-compose.https.example.yml}"
BACKUP_FILE="$1"

cd "$APP_DIR"

if [[ -f deploy/backup.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source deploy/backup.env
  set +a
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "Backup-Datei nicht gefunden: $BACKUP_FILE" >&2
  exit 1
fi

container_id="$(docker compose -f "$COMPOSE_FILE" ps -q nana)"
if [[ -z "$container_id" ]]; then
  echo "NANA container not found. Is docker compose running?" >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

case "$BACKUP_FILE" in
  *.sqlite.gz.enc)
    if [[ -z "${BACKUP_PASSPHRASE:-}" ]]; then
      echo "BACKUP_PASSPHRASE fehlt fuer verschluesseltes Backup." >&2
      exit 1
    fi
    openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
      -pass env:BACKUP_PASSPHRASE \
      -in "$BACKUP_FILE" \
      -out "$tmp_dir/nana-db.sqlite.gz"
    gzip -dc "$tmp_dir/nana-db.sqlite.gz" > "$tmp_dir/nana.db"
    ;;
  *.sqlite.gz)
    gzip -dc "$BACKUP_FILE" > "$tmp_dir/nana.db"
    ;;
  *.sqlite)
    cp "$BACKUP_FILE" "$tmp_dir/nana.db"
    ;;
  *)
    echo "Nicht unterstuetztes Backup-Format: $BACKUP_FILE" >&2
    exit 1
    ;;
esac

docker cp "$tmp_dir/nana.db" "$container_id:/tmp/nana-restore.sqlite"
docker compose -f "$COMPOSE_FILE" exec -T nana python - <<'PY'
import os
import shutil

shutil.copyfile("/tmp/nana-restore.sqlite", "/data/nana.db")
if os.path.exists("/tmp/nana-restore.sqlite"):
    os.remove("/tmp/nana-restore.sqlite")
PY
docker compose -f "$COMPOSE_FILE" restart nana

echo "Backup wiederhergestellt und NANA neu gestartet."

#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/NANA}"
COMPOSE_FILE="${COMPOSE_FILE:-deploy/docker-compose.https.example.yml}"
BACKUP_DIR="${BACKUP_DIR:-/opt/NANA/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
NANA_REQUIRE_ENCRYPTED_BACKUPS="${NANA_REQUIRE_ENCRYPTED_BACKUPS:-0}"

cd "$APP_DIR"

if [[ -f deploy/backup.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source deploy/backup.env
  set +a
fi

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

if [[ -n "${BACKUP_PASSPHRASE:-}" ]]; then
  encrypted_file="$backup_file.gz.enc"
  openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 \
    -pass env:BACKUP_PASSPHRASE \
    -in "$backup_file.gz" \
    -out "$encrypted_file"
  rm -f "$backup_file.gz"
  sha256sum "$encrypted_file" > "$encrypted_file.sha256"
  echo "Encrypted backup created: $encrypted_file"
elif [[ "$NANA_REQUIRE_ENCRYPTED_BACKUPS" == "1" ]]; then
  rm -f "$backup_file.gz"
  echo "BACKUP_PASSPHRASE fehlt; verschluesselte Backups sind erzwungen." >&2
  exit 1
else
  sha256sum "$backup_file.gz" > "$backup_file.gz.sha256"
  echo "WARNING: Backup wurde nicht zusaetzlich verschluesselt. BACKUP_PASSPHRASE setzen." >&2
fi

find "$BACKUP_DIR" -type f -name "nana-db-*.sqlite.gz" -mtime +"$KEEP_DAYS" -delete
find "$BACKUP_DIR" -type f -name "nana-db-*.sqlite.gz.sha256" -mtime +"$KEEP_DAYS" -delete
find "$BACKUP_DIR" -type f -name "nana-db-*.sqlite.gz.enc" -mtime +"$KEEP_DAYS" -delete
find "$BACKUP_DIR" -type f -name "nana-db-*.sqlite.gz.enc.sha256" -mtime +"$KEEP_DAYS" -delete

echo "Backup finished."

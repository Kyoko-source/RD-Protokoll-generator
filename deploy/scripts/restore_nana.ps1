param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [string]$ComposeFile = "deploy/docker-compose.https.example.yml"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $BackupFile)) {
    throw "Backup-Datei nicht gefunden: $BackupFile"
}

$containerId = docker compose -f $ComposeFile ps -q nana
if (-not $containerId) {
    throw "NANA-Container nicht gefunden. Laeuft docker compose?"
}

docker cp $BackupFile "$containerId`:/tmp/nana-restore.sqlite"
docker compose -f $ComposeFile exec -T nana python -c "import shutil; shutil.copyfile('/tmp/nana-restore.sqlite', '/data/nana.db')"
docker compose -f $ComposeFile exec -T nana python -c "import os; os.remove('/tmp/nana-restore.sqlite') if os.path.exists('/tmp/nana-restore.sqlite') else None"
docker compose -f $ComposeFile restart nana

Write-Host "Backup wiederhergestellt und NANA neu gestartet." -ForegroundColor Green

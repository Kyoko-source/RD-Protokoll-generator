param(
    [string]$ComposeFile = "deploy/docker-compose.https.example.yml",
    [string]$OutputDir = "backups"
)

$ErrorActionPreference = "Stop"

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupRoot = Join-Path (Get-Location) $OutputDir
$backupFile = Join-Path $backupRoot "nana-db-$timestamp.sqlite"

New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

$containerId = docker compose -f $ComposeFile ps -q nana
if (-not $containerId) {
    throw "NANA-Container nicht gefunden. Laeuft docker compose?"
}

docker compose -f $ComposeFile exec -T nana python -c "import shutil; shutil.copyfile('/data/nana.db', '/tmp/nana-backup.sqlite')"
docker cp "$containerId`:/tmp/nana-backup.sqlite" $backupFile
docker compose -f $ComposeFile exec -T nana python -c "import os; os.remove('/tmp/nana-backup.sqlite') if os.path.exists('/tmp/nana-backup.sqlite') else None"

Write-Host "Backup erstellt:" -ForegroundColor Green
Write-Host $backupFile

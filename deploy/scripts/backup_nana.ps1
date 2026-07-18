param(
    [string]$ComposeFile = "deploy/docker-compose.https.example.yml",
    [string]$OutputDir = "backups",
    [string]$BackupPassphrase = $env:BACKUP_PASSPHRASE,
    [switch]$AllowPlaintextDevelopmentBackup
)

$ErrorActionPreference = "Stop"

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupRoot = Join-Path (Get-Location) $OutputDir
$backupFile = Join-Path $backupRoot "nana-db-$timestamp.sqlite"

New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

if (-not $BackupPassphrase -and -not $AllowPlaintextDevelopmentBackup) {
    throw "BACKUP_PASSPHRASE fehlt. Fuer lokale Entwicklungsbackups explizit -AllowPlaintextDevelopmentBackup setzen."
}

$containerId = docker compose -f $ComposeFile ps -q nana
if (-not $containerId) {
    throw "NANA-Container nicht gefunden. Laeuft docker compose?"
}

docker compose -f $ComposeFile exec -T nana python -c "import shutil; shutil.copyfile('/data/nana.db', '/tmp/nana-backup.sqlite')"
docker cp "$containerId`:/tmp/nana-backup.sqlite" $backupFile
docker compose -f $ComposeFile exec -T nana python -c "import os; os.remove('/tmp/nana-backup.sqlite') if os.path.exists('/tmp/nana-backup.sqlite') else None"

if ($BackupPassphrase) {
    $openssl = Get-Command openssl -ErrorAction SilentlyContinue
    if (-not $openssl) {
        Remove-Item -LiteralPath $backupFile -Force -ErrorAction SilentlyContinue
        throw "OpenSSL wurde nicht gefunden. Ohne OpenSSL kann das Backup nicht verschluesselt werden."
    }

    $encryptedFile = "$backupFile.enc"
    $env:BACKUP_PASSPHRASE = $BackupPassphrase
    openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 -pass env:BACKUP_PASSPHRASE -in $backupFile -out $encryptedFile
    if ($LASTEXITCODE -ne 0) {
        Remove-Item -LiteralPath $backupFile -Force -ErrorAction SilentlyContinue
        throw "Backup-Verschluesselung fehlgeschlagen."
    }
    Remove-Item -LiteralPath $backupFile -Force
    Get-FileHash -Algorithm SHA256 $encryptedFile | ForEach-Object {
        "$($_.Hash)  $(Split-Path -Leaf $encryptedFile)" | Set-Content -Encoding ASCII "$encryptedFile.sha256"
    }
    Write-Host "Verschluesseltes Backup erstellt:" -ForegroundColor Green
    Write-Host $encryptedFile
} else {
    Get-FileHash -Algorithm SHA256 $backupFile | ForEach-Object {
        "$($_.Hash)  $(Split-Path -Leaf $backupFile)" | Set-Content -Encoding ASCII "$backupFile.sha256"
    }
    Write-Host "Unverschluesseltes Entwicklungsbackup erstellt:" -ForegroundColor Yellow
    Write-Host $backupFile
}

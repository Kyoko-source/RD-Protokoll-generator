param(
    [Parameter(Mandatory = $true)]
    [string]$Domain,

    [Parameter(Mandatory = $true)]
    [string]$Email,

    [string]$DataKey = ""
)

$ErrorActionPreference = "Stop"

$deployRoot = Split-Path -Parent $PSScriptRoot
$envTarget = Join-Path $deployRoot "env.production"
$caddyTarget = Join-Path $deployRoot "caddy\Caddyfile"

if (-not $DataKey) {
    $bytes = New-Object byte[] 48
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    $DataKey = [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

$envContent = @(
    "NANA_ENV=production",
    "NANA_DB_PATH=/data/nana.db",
    "NANA_DATA_KEY=$DataKey",
    "NANA_ALLOWED_ORIGINS=https://$Domain"
)

Set-Content -Path $envTarget -Value $envContent -Encoding UTF8

$caddyContent = Get-Content -Raw -Encoding UTF8 (Join-Path $deployRoot "caddy\Caddyfile.example")
$caddyContent = $caddyContent.Replace("admin@example.de", $Email).Replace("nana.example.de", $Domain)
Set-Content -Path $caddyTarget -Value $caddyContent -Encoding UTF8

Write-Host "Produktionskonfiguration erstellt:" -ForegroundColor Green
Write-Host $envTarget
Write-Host $caddyTarget
Write-Host ""
Write-Host "Wichtig: NANA_DATA_KEY sicher extern sichern. Ohne diesen Schluessel sind verschluesselte Patientendaten nicht wiederherstellbar." -ForegroundColor Yellow

param(
    [switch]$Frontend,
    [switch]$Docker,
    [string]$DockerTag = "nana-verify:local"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"
$frontendRoot = Join-Path $repoRoot "frontend"

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    $global:LASTEXITCODE = 0
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name fehlgeschlagen mit Exit-Code $LASTEXITCODE."
    }
    Write-Host "OK: $Name" -ForegroundColor Green
}

if (-not (Test-Path $pythonPath)) {
    throw "Python-Umgebung nicht gefunden: $pythonPath"
}

Invoke-Step "Python-Dateien kompilieren" {
    & $pythonPath -m py_compile `
        (Join-Path $repoRoot "backend\main.py") `
        (Join-Path $repoRoot "backend\schemas.py") `
        (Join-Path $repoRoot "storage.py") `
        (Join-Path $repoRoot "interfaces.py") `
        (Join-Path $repoRoot "hospital_finder.py") `
        (Join-Path $repoRoot "device_guides.py")
}

Invoke-Step "Unit- und API-Tests" {
    Push-Location $repoRoot
    try {
        & $pythonPath -m unittest discover -s tests -v
    } finally {
        Pop-Location
    }
}

Invoke-Step "Healthcheck importieren" {
    Push-Location $repoRoot
    try {
        & $pythonPath -c "from backend.main import health; data = health(); assert data['app'] == 'NANA'; assert data['database']['ok']; print(data['status'], data['ruleset_version'])"
    } finally {
        Pop-Location
    }
}

if ($Frontend) {
    Invoke-Step "Frontend Production Build" {
        Push-Location $frontendRoot
        try {
            npm.cmd run build
        } finally {
            Pop-Location
        }
    }
} else {
    Write-Host ""
    Write-Host "Frontend-Build uebersprungen. Separat pruefen mit: npm.cmd run build im Ordner frontend" -ForegroundColor Yellow
}

if ($Docker) {
    $dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $dockerCommand) {
        throw "Docker wurde nicht gefunden. Docker installieren oder ohne -Docker pruefen."
    }

    Invoke-Step "Docker Image Build" {
        Push-Location $repoRoot
        try {
            docker build -t $DockerTag .
        } finally {
            Pop-Location
        }
    }
}

Write-Host ""
Write-Host "NANA Verify erfolgreich abgeschlossen." -ForegroundColor Green

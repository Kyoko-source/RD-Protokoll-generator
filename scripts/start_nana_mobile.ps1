$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $repoRoot "frontend"
$nodePath = "C:\Program Files\nodejs"
$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"
$npmCmd = Join-Path $nodePath "npm.cmd"

if (Test-Path $nodePath) {
    $env:Path = "$nodePath;$env:Path"
}

if (-not (Test-Path $pythonPath)) {
    throw "Python-Umgebung nicht gefunden: $pythonPath"
}

if (-not (Test-Path $npmCmd)) {
    throw "Node/NPM nicht gefunden: $npmCmd"
}

function Stop-NanaPort {
    param([int]$Port)

    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
        $processId = $connection.OwningProcess
        if ($processId -and $processId -ne $PID) {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }
}

function Get-NanaLanAddress {
    $configs = Get-NetIPConfiguration | Where-Object {
        $_.IPv4DefaultGateway -and $_.IPv4Address
    }

    foreach ($config in $configs) {
        foreach ($address in $config.IPv4Address) {
            if ($address.IPAddress -and
                $address.IPAddress -ne "127.0.0.1" -and
                $address.IPAddress -notlike "169.254.*") {
                return $address.IPAddress
            }
        }
    }

    $fallback = Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
        $_.IPAddress -ne "127.0.0.1" -and $_.IPAddress -notlike "169.254.*"
    } | Select-Object -First 1

    return $fallback.IPAddress
}

Stop-NanaPort -Port 8000
Stop-NanaPort -Port 5173

Start-Process -FilePath $pythonPath `
    -ArgumentList "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000" `
    -WorkingDirectory $repoRoot `
    -WindowStyle Minimized

Start-Sleep -Seconds 2

Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", "set PATH=$nodePath;%PATH% && npm.cmd run dev -- --host 0.0.0.0 --port 5173" `
    -WorkingDirectory $frontendRoot `
    -WindowStyle Minimized

Start-Sleep -Seconds 3
$cacheBuster = Get-Date -Format "yyyyMMddHHmmss"
$lanAddress = Get-NanaLanAddress
$localUrl = "http://127.0.0.1:5173/?nana=$cacheBuster"
$mobileUrl = "http://$lanAddress`:5173/?nana=$cacheBuster"

Start-Process $localUrl

Write-Host ""
Write-Host "NANA ist im WLAN gestartet." -ForegroundColor Green
Write-Host "Handy-Adresse:" -ForegroundColor Cyan
Write-Host $mobileUrl -ForegroundColor White
Write-Host ""
Write-Host "PC und Handy muessen im gleichen WLAN sein. Falls Windows fragt, den Netzwerkzugriff fuer Python/Node erlauben." -ForegroundColor Yellow
Write-Host "Dieses Fenster kann offen bleiben, solange du die Adresse ablesen moechtest."

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

Stop-NanaPort -Port 8000
Stop-NanaPort -Port 5173

Start-Process -FilePath $pythonPath `
    -ArgumentList "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory $repoRoot `
    -WindowStyle Minimized

Start-Sleep -Seconds 2

Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", "set PATH=$nodePath;%PATH% && npm.cmd run dev -- --host 127.0.0.1 --port 5173" `
    -WorkingDirectory $frontendRoot `
    -WindowStyle Minimized

Start-Sleep -Seconds 3
$cacheBuster = Get-Date -Format "yyyyMMddHHmmss"
Start-Process "http://127.0.0.1:5173/?nana=$cacheBuster"

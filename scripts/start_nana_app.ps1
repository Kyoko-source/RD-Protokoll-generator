$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $repoRoot "frontend"
$nodePath = "C:\Program Files\nodejs"

if (Test-Path $nodePath) {
    $env:Path = "$nodePath;$env:Path"
}

Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory $repoRoot `
    -WindowStyle Minimized

Start-Sleep -Seconds 2

Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", "npm run dev -- --host 127.0.0.1 --port 5173" `
    -WorkingDirectory $frontendRoot `
    -WindowStyle Minimized

Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:5173"

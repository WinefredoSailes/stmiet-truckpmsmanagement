$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $projectDir "truck_pms\venv\Scripts\python.exe"
$managePy = Join-Path $projectDir "truck_pms\manage.py"

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    & "C:\Users\Seven Trent\AppData\Local\Programs\Python\Python313\python.exe" -m venv (Join-Path $projectDir "truck_pms\venv")
    & $venvPython -m pip install -r (Join-Path $projectDir "truck_pms\requirements.txt") | Out-Null
}

Write-Host "Starting Truck PMS server at http://0.0.0.0:8000" -ForegroundColor Green
Write-Host "Access from this machine: http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "Access from local network: http://<your-ip>:8000" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop`n" -ForegroundColor Yellow

& $venvPython $managePy runserver 0.0.0.0:8000

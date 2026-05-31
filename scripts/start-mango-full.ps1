# Start Mango desktop UI (Electron) + Python voice runtime.
Set-Location $PSScriptRoot\..

if (-not (Test-Path .\mango-app\package.json)) {
    Write-Error "mango-app not found. Run from the Mango repository root."
    exit 1
}

if (-not (Test-Path .\.env)) {
    Write-Host "No .env found. Run .\scripts\setup-env.ps1 first." -ForegroundColor Yellow
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Error "Node.js not found on PATH. Install Node 18+ for the desktop UI."
    exit 1
}

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    Write-Host "Creating Python venv and installing runtime..." -ForegroundColor Yellow
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    .\.venv\Scripts\pip.exe install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if (-not (Test-Path .\mango-app\node_modules)) {
    Write-Host "Installing mango-app npm dependencies..." -ForegroundColor Yellow
    Push-Location mango-app
    npm install
    if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
    Pop-Location
}

Write-Host "Mango desktop starting (close the window to quit voice + UI)..." -ForegroundColor Cyan
Write-Host "Terminal-only voice: python -m mango.main" -ForegroundColor DarkGray
Push-Location mango-app
npm run dev
$code = $LASTEXITCODE
Pop-Location
exit $code

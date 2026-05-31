# Quick sanity: config/doctor + unit tests (no mic or live Groq chat).
Set-Location $PSScriptRoot\..

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    Write-Error "Missing .venv. Run: python -m venv .venv; pip install -r requirements.txt -r requirements-dev.txt"
    exit 1
}

.\.venv\Scripts\Activate.ps1
$env:PYTHONUNBUFFERED = "1"

Write-Host "=== mango --doctor ===" -ForegroundColor Cyan
python -m mango --doctor
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n=== pytest tests/ -q ===" -ForegroundColor Cyan
python -m pytest tests/ -q
exit $LASTEXITCODE

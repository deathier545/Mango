# Quick verification: doctor + open_app resolution smoke (no launches by default).
Set-Location $PSScriptRoot
if (-not (Test-Path .\.venv\Scripts\Activate.ps1)) {
    Write-Error "Missing .venv. Run: python -m venv .venv; pip install -r requirements.txt -r requirements-dev.txt"
    exit 1
}
.\.venv\Scripts\Activate.ps1
$env:PYTHONUNBUFFERED = "1"
Write-Host "=== mango --doctor ===" -ForegroundColor Cyan
python -m mango --doctor
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "`n=== smoke_open_apps (dry-run) ===" -ForegroundColor Cyan
python scripts\smoke_open_apps.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "`n=== pytest (tests/) ===" -ForegroundColor Cyan
python -m pytest tests/ -q
exit $LASTEXITCODE

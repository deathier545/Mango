# Mango with Python development mode (-X dev + PYTHONDEVMODE).
# Compatible with Windows PowerShell 5.1 and PowerShell 7+.
Set-Location $PSScriptRoot
if (-not (Test-Path .\.venv\Scripts\Activate.ps1)) {
    Write-Error "Missing .venv. Run: python -m venv .venv; pip install -r requirements.txt -r requirements-dev.txt"
    exit 1
}
.\.venv\Scripts\Activate.ps1
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONDEVMODE = "1"
$env:MANGO_LOG_LEVEL = "DEBUG"
python -X dev -m mango.main

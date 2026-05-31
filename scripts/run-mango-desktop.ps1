# Mango desktop shell (Tk window + voice core subprocess).
Set-Location $PSScriptRoot\..
if (-not (Test-Path .\.venv\Scripts\Activate.ps1)) {
    Write-Error "Missing .venv. Run: python -m venv .venv; pip install -r requirements.txt"
    exit 1
}
.\.venv\Scripts\Activate.ps1
$env:PYTHONUNBUFFERED = "1"
python -m mango --desktop

# Bootstrap .env from .env.example and show recommended defaults.
Set-Location $PSScriptRoot\..

$example = Join-Path (Get-Location) ".env.example"
$envFile = Join-Path (Get-Location) ".env"
$recommended = Join-Path (Get-Location) "docs\recommended.env"

if (-not (Test-Path $example)) {
    Write-Error ".env.example not found. Run from the Mango repository root."
    exit 1
}

if (-not (Test-Path $envFile)) {
    Copy-Item $example $envFile
    Write-Host "Created .env from .env.example" -ForegroundColor Green
} else {
    Write-Host ".env already exists - not overwritten." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Edit .env and set GROQ_API_KEY= from https://console.groq.com/"
Write-Host "  2. Optional: merge tips from docs\recommended.env"
if (Test-Path $recommended) {
    Write-Host "     Get-Content docs\recommended.env"
}
Write-Host "  3. python -m mango --doctor"
Write-Host "  4. Terminal voice: python -m mango.main"
Write-Host "  5. Desktop UI:    .\scripts\start-mango-full.ps1"
Write-Host ""
Write-Host "Push-to-talk may need an elevated PowerShell if HOTKEY fails globally." -ForegroundColor DarkYellow

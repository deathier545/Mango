# Run after WSL is installed OR use for Colab onnx drop-in
param(
  [switch]$SkipWsl,
  [switch]$OnlyEnv
)
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot

& "$here\scripts\ensure-acav-download.ps1"

if ($OnlyEnv) {
  & "$here\apply-mango-wake-env.ps1"
  exit $LASTEXITCODE
}

if (-not $SkipWsl) {
  $wslOk = $false
  try { wsl -e true 2>$null; if ($LASTEXITCODE -eq 0) { $wslOk = $true } } catch {}
  if ($wslOk) {
    & "$here\run-after-reboot.ps1"
    exit $LASTEXITCODE
  }
}

Write-Host ""
Write-Host "WSL is not available. Do one of:" -ForegroundColor Yellow
Write-Host "  1) Admin PowerShell: .\install-wsl.ps1  -> reboot -> .\run-after-reboot.ps1"
Write-Host "  2) Colab train, save mango.onnx to output\mango\, then: .\apply-mango-wake-env.ps1"
Write-Host ""
if (Test-Path (Join-Path $here "output\mango\mango.onnx")) {
  & "$here\apply-mango-wake-env.ps1"
}

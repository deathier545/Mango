# Start wake-word training (run after Ubuntu first-launch setup is done).
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
Set-Location $here

Write-Host "Checking Ubuntu WSL..."
$test = wsl -d Ubuntu -u root -e true 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Host ""
  Write-Host "Ubuntu is not ready yet." -ForegroundColor Yellow
  Write-Host "1. Open 'Ubuntu' from the Start menu."
  Write-Host "2. Finish setup (username + password) if prompted."
  Write-Host "3. Close Ubuntu, then run: .\start-now.ps1"
  exit 1
}

Write-Host "Ubuntu OK. Starting full pipeline (many hours)..." -ForegroundColor Green
Write-Host "Log: $here\logs\pipeline.log"
New-Item -ItemType Directory -Force -Path "$here\logs" | Out-Null

$log = "$here\logs\pipeline.log"
Start-Process powershell -ArgumentList @(
  "-NoProfile", "-ExecutionPolicy", "Bypass",
  "-Command", "& '$here\run-after-reboot.ps1' *>&1 | Tee-Object -FilePath '$log'"
) -WindowStyle Normal

Write-Host "Pipeline started in a new window. Watch logs\pipeline.log"

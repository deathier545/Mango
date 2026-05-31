# Run once after reboot (Ubuntu WSL was installed).
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot

Write-Host "Checking WSL..."
wsl -d Ubuntu -e echo "Ubuntu OK"
if ($LASTEXITCODE -ne 0) {
  Write-Host "Ubuntu not ready. Open Ubuntu from Start menu once to finish setup, then re-run this script."
  exit 1
}

# Fix ACAV file name if still .part
$data = Join-Path $here "data"
$final = Join-Path $data "openwakeword_features_ACAV100M_2000_hrs_16bit.npy"
$acav = Join-Path $data "acav_complete.npy"
$part = Join-Path $data "openwakeword_features_ACAV100M_2000_hrs_16bit.npy.part"
if (Test-Path $acav) {
  Remove-Item $final, $part -Force -ErrorAction SilentlyContinue
  Rename-Item $acav (Split-Path $final -Leaf)
  Write-Host "Renamed acav_complete.npy -> expected name."
} elseif (Test-Path $part) {
  Remove-Item $final -Force -ErrorAction SilentlyContinue
  Rename-Item $part (Split-Path $final -Leaf)
  Write-Host "Renamed .part -> expected name."
}
$gb = [math]::Round((Get-Item $final -ErrorAction SilentlyContinue).Length / 1GB, 2)
Write-Host "ACAV features: ${gb} GB (want ~16)"

$wslPath = (wsl wslpath -a $here).Trim()
Write-Host "Running setup in WSL: $wslPath"
wsl -d Ubuntu bash -lc "cd '$wslPath' && sed -i 's/\r$//' scripts/*.sh && chmod +x scripts/*.sh && bash scripts/setup-environment.sh"

Write-Host ""
Write-Host "Setup complete. Next (each step takes a long time):"
Write-Host "  .\run-download-data.ps1"
Write-Host "  .\run-01-generate-clips.ps1"
Write-Host "  .\run-02-augment-clips.ps1"
Write-Host "  .\run-03-train-model.ps1"

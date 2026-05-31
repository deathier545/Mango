# Run full wake-word pipeline in WSL after install-wsl.ps1 + reboot
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot

if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) {
  Write-Host "WSL not found. Run install-wsl.ps1 as Administrator first." -ForegroundColor Red
  exit 1
}

$distros = @(wsl -l -q 2>$null)
if ($distros.Count -eq 0) {
  Write-Host "No WSL distro. Run: wsl --install" -ForegroundColor Red
  exit 1
}

$wslPath = (wsl wslpath -a $here).Trim()
Write-Host "Wake word training root (WSL): $wslPath"

wsl bash -lc @"
set -euo pipefail
cd '$wslPath'
sed -i 's/\r$//' scripts/*.sh 2>/dev/null || true
chmod +x scripts/*.sh

if [ ! -f .venv-train/bin/activate ]; then
  echo '=== Setup ==='
  bash scripts/setup-environment.sh
fi

echo '=== Data (skip if already complete) ==='
bash scripts/00-download-data.sh || true

echo '=== Step 1: generate_clips (hours) ==='
source .venv-train/bin/activate
python vendor/openwakeword/openwakeword/train.py --training_config config/mango.yml --generate_clips

echo '=== Step 2: augment_clips ==='
python vendor/openwakeword/openwakeword/train.py --training_config config/mango.yml --augment_clips

echo '=== Step 3: train_model ==='
python vendor/openwakeword/openwakeword/train.py --training_config config/mango.yml --train_model

echo 'Done. ONNX:' 
ls -la output/mango/*.onnx 2>/dev/null || ls -la output/mango/mango/*.onnx 2>/dev/null || find output -name '*.onnx'
"@

& "$here\apply-mango-wake-env.ps1"

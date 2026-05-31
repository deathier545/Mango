# Windows training environment (Piper may fail on Windows — WSL is preferred)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path "vendor\openwakeword")) {
  Write-Host "Cloning openWakeWord..."
  git clone --depth 1 https://github.com/dscripka/openWakeWord.git vendor\openwakeword
}

if (-not (Test-Path "piper-sample-generator")) {
  Write-Host "Cloning piper-sample-generator..."
  git clone --depth 1 https://github.com/rhasspy/piper-sample-generator.git piper-sample-generator
  New-Item -ItemType Directory -Force -Path "piper-sample-generator\models" | Out-Null
  $pt = "piper-sample-generator\models\en_US-libritts_r-medium.pt"
  if (-not (Test-Path $pt)) {
    Invoke-WebRequest -Uri "https://github.com/rhasspy/piper-sample-generator/releases/download/v2.0.0/en_US-libritts_r-medium.pt" -OutFile $pt
  }
}

$py = Join-Path $Root ".venv-train\Scripts\python.exe"
if (-not (Test-Path $py)) {
  py -3.11 -m venv (Join-Path $Root ".venv-train")
}

& $py -m pip install -U pip wheel
& $py -m pip install pyyaml tqdm "scipy>=1.10,<1.14" numpy datasets mutagen torchinfo torchmetrics `
  speechbrain audiomentations torch-audiomentations acoustics pronouncing deep-phonemizer torchcodec

# Piper stack — often Linux-only; try anyway
try {
  & $py -m pip install piper-phonemize webrtcvad
} catch {
  Write-Warning "piper-phonemize install failed (expected on some Windows builds). Use WSL or Colab for step 1."
}

& $py -m pip install -e (Join-Path $Root "vendor\openwakeword")

$modelsDir = Join-Path $Root "vendor\openwakeword\openwakeword\resources\models"
New-Item -ItemType Directory -Force -Path $modelsDir | Out-Null
$base = "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1"
foreach ($f in @("embedding_model.onnx", "embedding_model.tflite", "melspectrogram.onnx", "melspectrogram.tflite")) {
  $dest = Join-Path $modelsDir $f
  if (-not (Test-Path $dest)) {
    Invoke-WebRequest -Uri "$base/$f" -OutFile $dest
  }
}

Write-Host "Setup done. Python: $py"

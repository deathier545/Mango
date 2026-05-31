#!/usr/bin/env bash
# One-time environment setup (Linux or WSL2). Piper TTS generation is not supported on native Windows.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_CACHE_DIR=1

if ! python3 -m venv --help >/dev/null 2>&1; then
  echo "ERROR: python3-venv missing. Run once as root:"
  echo "  wsl -d Ubuntu -u root bash scripts/install-system-packages.sh"
  exit 1
fi

TRAIN_PY=python3
echo "==> Training Python: $("$TRAIN_PY" --version)"

if [ ! -d vendor/openwakeword ]; then
  echo "==> Cloning openWakeWord"
  git clone --depth 1 https://github.com/dscripka/openWakeWord.git vendor/openwakeword
fi

if [ ! -d piper-sample-generator ]; then
  echo "==> Cloning piper-sample-generator"
  git clone --depth 1 https://github.com/rhasspy/piper-sample-generator.git piper-sample-generator
  mkdir -p piper-sample-generator/models
  wget -O piper-sample-generator/models/en_US-libritts_r-medium.pt \
    "https://github.com/rhasspy/piper-sample-generator/releases/download/v2.0.0/en_US-libritts_r-medium.pt"
fi

VENV="${JARVIS_WAKE_VENV:-$ROOT/.venv-train}"
rm -rf "$VENV"
"$TRAIN_PY" -m venv "$VENV"
# shellcheck disable=SC1091
. "$VENV/bin/activate"
pip install -U pip wheel

pip install -r ./piper-sample-generator/requirements.txt
# CPU torch only (CUDA wheels crash with Illegal instruction in many WSL setups)
pip install --force-reinstall torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install soundfile torchcodec
pip install 'audiomentations==0.33.0' 'scipy<1.15' 'torch-audiomentations>=0.12.0'
pip install mutagen==1.47.0 torchinfo==1.8.0 torchmetrics==1.2.0 \
  speechbrain==0.5.14 acoustics==0.2.6 \
  pronouncing==0.2.0 'datasets>=2.19.0' 'fsspec>=2023.1.0,<=2024.9.0' deep-phonemizer==0.0.19 pyyaml tqdm scipy

pip install -e ./vendor/openwakeword

mkdir -p vendor/openwakeword/openwakeword/resources/models
BASE="https://github.com/dscripka/openWakeWord/releases/download/v0.5.1"
for f in embedding_model.onnx embedding_model.tflite melspectrogram.onnx melspectrogram.tflite; do
  if [ ! -f "vendor/openwakeword/openwakeword/resources/models/$f" ]; then
    wget -O "vendor/openwakeword/openwakeword/resources/models/$f" "$BASE/$f"
  fi
done

echo ""
echo "Setup complete. Activate with: source $VENV/bin/activate"
echo "Then: bash scripts/00-download-data.sh"
echo "Then run 01, 02, 03 in order."

#!/usr/bin/env bash
# Full wake-word training: data -> generate -> augment -> train
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
sed -i 's/\r$//' scripts/*.sh 2>/dev/null || true
chmod +x scripts/*.sh
mkdir -p logs
exec >>logs/pipeline.log 2>&1

echo "=== Training run $(date) ==="

export JARVIS_WAKE_VENV="${JARVIS_WAKE_VENV:-$HOME/.jarvis-wake-venv}"
bash scripts/ensure-venv.sh
# shellcheck disable=SC1091
. "$JARVIS_WAKE_VENV/bin/activate"
cp -n piper-sample-generator/models/en-us-libritts-high.pt.json \
  piper-sample-generator/models/en_US-libritts_r-medium.pt.json 2>/dev/null || true
python -c "import torch, openwakeword, soundfile; print('torch', torch.__version__)"

bash scripts/00-download-data.sh

mkdir -p output/mango

echo "=== Step 1: generate_clips (hours) ==="
python vendor/openwakeword/openwakeword/train.py --training_config config/mango.yml --generate_clips

echo "=== Step 2: augment ==="
python vendor/openwakeword/openwakeword/train.py --training_config config/mango.yml --augment_clips

echo "=== Step 3: train ==="
python vendor/openwakeword/openwakeword/train.py --training_config config/mango.yml --train_model

echo "=== Done ==="
find output -name '*.onnx' -ls

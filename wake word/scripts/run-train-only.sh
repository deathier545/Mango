#!/usr/bin/env bash
# Resume training after generate_clips + augment_clips completed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
sed -i 's/\r$//' scripts/*.sh 2>/dev/null || true
mkdir -p logs
exec >>logs/pipeline.log 2>&1

echo "=== Step 3 only (train_model) $(date) ==="

export JARVIS_WAKE_VENV="${JARVIS_WAKE_VENV:-$HOME/.jarvis-wake-venv}"
export OWW_TRAIN_NUM_WORKERS="${OWW_TRAIN_NUM_WORKERS:-0}"
bash scripts/ensure-venv.sh
# shellcheck disable=SC1091
. "$JARVIS_WAKE_VENV/bin/activate"

python vendor/openwakeword/openwakeword/train.py \
  --training_config config/mango.yml \
  --train_model

echo "=== Step 3 done $(date) ==="
find output -name '*.onnx' -ls 2>/dev/null || true

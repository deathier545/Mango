#!/usr/bin/env bash
# Step 3 — same as notebook cell: train.py --train_model
# Output: output/mango/mango.onnx (and .tflite) when using config/mango.yml
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
CONFIG="${1:-config/mango.yml}"

if [ ! -f .venv-train/bin/activate ]; then
  echo "Run scripts/setup-environment.sh first." >&2
  exit 1
fi
# shellcheck disable=SC1091
source .venv-train/bin/activate

exec python vendor/openwakeword/openwakeword/train.py \
  --training_config "$CONFIG" \
  --train_model

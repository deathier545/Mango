#!/usr/bin/env bash
# Run inside Ubuntu: cd "/mnt/c/Users/Dylan/jarvis/wake word" && bash scripts/run-all.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
sed -i 's/\r$//' scripts/*.sh 2>/dev/null || true
chmod +x scripts/*.sh

need_setup() {
  [ ! -f .venv-train/bin/activate ] && return 0
  .venv-train/bin/python -c "import openwakeword" 2>/dev/null || return 0
  return 1
}

if need_setup; then
  echo "=== Setup ==="
  bash scripts/setup-environment.sh
fi
. .venv-train/bin/activate

echo "=== Data ==="
bash scripts/00-download-data.sh || true

echo "=== Step 1: generate_clips (hours) ==="
python vendor/openwakeword/openwakeword/train.py --training_config config/mango.yml --generate_clips

echo "=== Step 2: augment ==="
python vendor/openwakeword/openwakeword/train.py --training_config config/mango.yml --augment_clips

echo "=== Step 3: train ==="
python vendor/openwakeword/openwakeword/train.py --training_config config/mango.yml --train_model

echo "=== Done ==="
find output -name '*.onnx' -ls

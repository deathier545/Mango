#!/usr/bin/env bash
# Run after setup-environment.sh (or if run-all died mid-setup). Data + train only.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
sed -i 's/\r$//' scripts/*.sh 2>/dev/null || true

echo "Waiting for venv + openwakeword..."
for _ in $(seq 1 240); do
  if [ -f .venv-train/bin/python ] && .venv-train/bin/python -c "import openwakeword" 2>/dev/null; then
    break
  fi
  if ! pgrep -f setup-environment.sh >/dev/null 2>&1; then
    if [ -f .venv-train/bin/python ] && ! .venv-train/bin/python -c "import openwakeword" 2>/dev/null; then
      echo "Setup failed or incomplete — re-running setup-environment.sh"
      bash scripts/setup-environment.sh
      break
    fi
  fi
  sleep 30
done

. .venv-train/bin/activate
python -c "import openwakeword"

exec >>logs/pipeline.log 2>&1
echo "=== Continue pipeline $(date) ==="

bash scripts/00-download-data.sh || true

echo "=== Step 1: generate_clips (hours) ==="
python vendor/openwakeword/openwakeword/train.py --training_config config/mango.yml --generate_clips

echo "=== Step 2: augment ==="
python vendor/openwakeword/openwakeword/train.py --training_config config/mango.yml --augment_clips

echo "=== Step 3: train ==="
python vendor/openwakeword/openwakeword/train.py --training_config config/mango.yml --train_model

echo "=== Done ==="
find output -name '*.onnx' -ls

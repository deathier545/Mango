#!/usr/bin/env bash
# Step 2 — same as notebook cell: train.py --augment_clips
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
  --augment_clips

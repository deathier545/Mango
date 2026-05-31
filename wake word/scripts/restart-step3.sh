#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export JARVIS_WAKE_VENV="${JARVIS_WAKE_VENV:-$HOME/.jarvis-wake-venv}"
# shellcheck disable=SC1091
. "$JARVIS_WAKE_VENV/bin/activate"
pip install -q onnxscript onnx
python -c "import onnxscript"
exec bash scripts/run-train-only.sh

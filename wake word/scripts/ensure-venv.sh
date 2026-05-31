#!/usr/bin/env bash
# Use Linux-native venv (faster, avoids broken torch on /mnt/c partial installs)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${JARVIS_WAKE_VENV:-$HOME/.jarvis-wake-venv}"

if [ ! -f "$VENV/bin/activate" ]; then
  echo "Creating venv at $VENV (one-time, ~20-30 min)"
  export JARVIS_WAKE_VENV="$VENV"
  cd "$ROOT"
  bash scripts/setup-environment.sh
else
  # shellcheck disable=SC1091
  . "$VENV/bin/activate"
  cd "$ROOT"
  if ! python -c "import torch" 2>/dev/null; then
    echo "Repairing CPU torch in $VENV"
    pip install --force-reinstall --no-cache-dir torch torchaudio \
      --index-url https://download.pytorch.org/whl/cpu
  fi
fi

if ! python -c "import onnxscript" 2>/dev/null; then
  echo "Installing onnxscript for ONNX export after training"
  pip install -q onnxscript onnx
fi

python -c "import torch, openwakeword, onnxscript; print('venv OK', torch.__version__)"

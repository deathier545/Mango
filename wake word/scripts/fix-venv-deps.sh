#!/usr/bin/env bash
# Fix Python 3.14 package combos that crash train.py on WSL
set -euo pipefail
VENV="${JARVIS_WAKE_VENV:-$HOME/.jarvis-wake-venv}"
# shellcheck disable=SC1091
. "$VENV/bin/activate"
pip install 'audiomentations==0.33.0' 'scipy<1.15' 'torch-audiomentations>=0.12.0'
python -c "import openwakeword.train; print('train.py imports OK')"

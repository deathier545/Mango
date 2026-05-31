#!/usr/bin/env bash
# One command: fix deps + run full training pipeline (run inside WSL)
set -euo pipefail
cd "$(dirname "$0")"
sed -i 's/\r$//' scripts/*.sh 2>/dev/null || true
chmod +x scripts/*.sh

export PIP_NO_CACHE_DIR=1
. .venv-train/bin/activate

echo "==> CPU PyTorch + pyarrow"
pip install --force-reinstall --no-cache-dir torch torchaudio \
  --index-url https://download.pytorch.org/whl/cpu
pip install 'pyarrow>=14,<21'
python -c "import torch, pyarrow, openwakeword; print('torch', torch.__version__, 'pyarrow', pyarrow.__version__)"

exec bash scripts/continue-pipeline.sh

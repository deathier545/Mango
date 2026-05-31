#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
sed -i 's/\r$//' scripts/*.sh 2>/dev/null || true
. .venv-train/bin/activate
export PIP_NO_CACHE_DIR=1
echo "==> CPU torch + compatible pyarrow"
pip install --force-reinstall torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install 'pyarrow>=14,<21'
python -c "import torch; import pyarrow; print('torch', torch.__version__, 'pyarrow', pyarrow.__version__)"
bash scripts/continue-pipeline.sh

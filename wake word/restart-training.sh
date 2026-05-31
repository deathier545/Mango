#!/usr/bin/env bash
cd "$(dirname "$0")"
pkill -f run-training.sh 2>/dev/null || true
pkill -f 'train.py.*mango.yml' 2>/dev/null || true
sleep 1
sed -i 's/\r$//' scripts/*.sh 2>/dev/null || true
chmod +x scripts/*.sh
export JARVIS_WAKE_VENV="${JARVIS_WAKE_VENV:-$HOME/.jarvis-wake-venv}"
bash scripts/ensure-venv.sh
# shellcheck disable=SC1091
. "$JARVIS_WAKE_VENV/bin/activate"
cp -n piper-sample-generator/models/en-us-libritts-high.pt.json \
  piper-sample-generator/models/en_US-libritts_r-medium.pt.json 2>/dev/null || true
echo "=== RESTART $(date) ===" >> logs/pipeline.log
nohup bash scripts/run-training.sh >> logs/pipeline.log 2>&1 &
echo "Started PID $!"
sleep 5
pgrep -af run-training || true
pgrep -af 'train.py.*mango' || true
tail -10 logs/pipeline.log

#!/usr/bin/env bash
ONNX="$(cd "$(dirname "$0")/.." && pwd)/output/mango/mango.onnx"
LOG="$(cd "$(dirname "$0")/.." && pwd)/logs/pipeline.log"
for i in $(seq 1 60); do
  if [[ -f "$ONNX" ]]; then
    ls -la "$ONNX"
    exit 0
  fi
  if ! pgrep -f 'vendor/openwakeword/openwakeword/train.py.*train_model' >/dev/null 2>&1; then
    echo "train.py exited without onnx"
    grep -aE 'Step 3 done|Saving ONNX|Error|Traceback|ModuleNotFound' "$LOG" | tail -8
    exit 1
  fi
  sleep 60
done
grep -a 'Training:' "$LOG" | tail -1 | tr -cd '\11\12\15\40-\176' | tail -c 120
echo "still running after 60 min"
exit 2

#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p data

PY=python3
if [ -n "${JARVIS_WAKE_VENV:-}" ] && [ -f "${JARVIS_WAKE_VENV}/bin/python" ]; then
  PY="${JARVIS_WAKE_VENV}/bin/python"
elif [ -f .venv-train/bin/python ]; then
  PY=".venv-train/bin/python"
fi

echo "==> Augmentation audio (MIT RIRs + FMA)"
"$PY" scripts/download-augmentation-data.py

echo "==> openWakeWord precomputed features"
if [ -f data/acav_complete.npy ]; then
  echo "    acav_complete.npy present — skipping 16GB duplicate download"
else
  if [ ! -f data/openwakeword_features_ACAV100M_2000_hrs_16bit.npy ]; then
    wget -O data/openwakeword_features_ACAV100M_2000_hrs_16bit.npy \
      "https://huggingface.co/datasets/davidscripka/openwakeword_features/resolve/main/openwakeword_features_ACAV100M_2000_hrs_16bit.npy"
  fi
fi
if [ ! -f data/validation_set_features.npy ]; then
  wget -O data/validation_set_features.npy \
    "https://huggingface.co/datasets/davidscripka/openwakeword_features/resolve/main/validation_set_features.npy"
fi

echo "Data download step finished."

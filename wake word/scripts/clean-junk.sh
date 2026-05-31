#!/usr/bin/env bash
# Remove incomplete duplicates; keep acav_complete.npy and validation_set_features.npy
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

STUB="data/openwakeword_features_ACAV100M_2000_hrs_16bit.npy"
ACAV="data/acav_complete.npy"
if [ -f "$ACAV" ] && [ -f "$STUB" ]; then
  stub_gb=$(du -b "$STUB" | awk '{print int($1/1073741824)}')
  acav_gb=$(du -b "$ACAV" | awk '{print int($1/1073741824)}')
  if [ "$stub_gb" -lt 10 ] && [ "$acav_gb" -ge 10 ]; then
    echo "Removing incomplete stub: $STUB (${stub_gb}GB vs acav ${acav_gb}GB)"
    rm -f "$STUB"
  fi
fi
rm -f data/*.part data/*.crdownload 2>/dev/null || true
echo "Clean done."

#!/usr/bin/env bash
# Run as root once: wsl -d Ubuntu -u root bash scripts/install-system-packages.sh
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y \
  python3-venv python3-pip git wget build-essential \
  espeak-ng libespeak-ng-dev libspeexdsp-dev ffmpeg libsndfile1
echo "System packages OK."

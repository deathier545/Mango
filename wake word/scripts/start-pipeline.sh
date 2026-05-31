#!/usr/bin/env bash
# Run full pipeline; logs to logs/pipeline.log (safe from PowerShell stderr quirks)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p logs
sed -i 's/\r$//' scripts/*.sh 2>/dev/null || true
chmod +x scripts/*.sh

bash scripts/clean-junk.sh || true

if [ "$(id -u)" -ne 0 ]; then
  echo "==> System packages (root)..."
  if command -v sudo >/dev/null && sudo -n true 2>/dev/null; then
    sudo bash scripts/install-system-packages.sh
  else
    echo "WARN: run once: wsl -d Ubuntu -u root bash scripts/install-system-packages.sh"
  fi
fi

exec >>logs/pipeline.log 2>&1
echo "=== Pipeline started $(date -Iseconds) ==="
bash scripts/run-all.sh
echo "=== Pipeline finished $(date -Iseconds) exit=$? ==="

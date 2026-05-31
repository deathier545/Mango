"""Resolve (and optionally launch) apps for open_app smoke testing.

From repo root::

    python scripts/smoke_open_apps.py

Actually start each app (many windows)::

    set MANGO_OPEN_APPS_FOR_REAL=1
    python scripts/smoke_open_apps.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mango.tools.open_app import resolve_target, run  # noqa: E402


def main() -> int:
    apps = [
        "notepad",
        "calculator",
        "spotify",
        "chrome",
        "brave",
        "edge",
        "discord",
        "slack",
        "teams",
        "zoom",
        "steam",
        "vlc",
        "vscode",
        "whatsapp",
        "obs",
        "signal",
        "telegram",
        "settings",
        "terminal",
    ]
    real = os.getenv("MANGO_OPEN_APPS_FOR_REAL", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    print(f"Mode: {'LAUNCH' if real else 'DRY-RUN (resolve only)'}")
    print("Set MANGO_OPEN_APPS_FOR_REAL=1 to actually start each app.\n")

    failures = 0
    for name in apps:
        target, detail = resolve_target(name)
        if target:
            print(f"OK  {name:12} -> {target[:90]}{'…' if len(target) > 90 else ''}  ({detail})")
            if real:
                msg = run(name)
                print(f"     {msg}")
        else:
            print(f"MISS {name:12} -> {detail}")
            failures += 1

    print(f"\nResolved {len(apps) - failures}/{len(apps)} (misses are OK if not installed).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

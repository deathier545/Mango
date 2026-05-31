"""Allow ``python -m mango`` and ``python -m mango --doctor`` without loading pygame first."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    env = root / ".env"
    if env.is_file():
        load_dotenv(dotenv_path=env, override=True, encoding="utf-8-sig")

    if "--doctor" in sys.argv:
        from mango.doctor import run_doctor
        from mango.logging_setup import setup_logging

        setup_logging()
        raise SystemExit(run_doctor())

    if "--oww-mic-probe" in sys.argv:
        from mango.logging_setup import setup_logging
        from mango.wake.oww_mic_probe import main as oww_mic_probe_main

        setup_logging()
        raise SystemExit(oww_mic_probe_main())

    if "--discord-voice" in sys.argv:
        import asyncio

        from mango.logging_setup import setup_logging

        setup_logging()
        from mango.integrations.discord.discord_voice_bot import amain

        asyncio.run(amain())
        raise SystemExit(0)

    if "--smart" in sys.argv:
        from mango.smart.desktop_smart import main as smart_main

        raise SystemExit(smart_main(sys.argv[sys.argv.index("--smart") + 1 :]))

    if "--desktop" in sys.argv:
        import multiprocessing

        multiprocessing.freeze_support()
        from mango.desktop.desktop_app import run_desktop_app

        run_desktop_app()
        raise SystemExit(0)

    from mango.main import main

    main()

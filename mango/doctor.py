"""Lightweight environment checks without importing pygame / mic stack.

Run from project root::

    python -m mango --doctor
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from mango.presets import PRESET_PROMPT_SUFFIX, known_presets


def run_doctor() -> int:
    root = Path(__file__).resolve().parent.parent
    env_path = root / ".env"

    env_ok = "found" if env_path.is_file() else "missing"
    print(f"Project root: {root}")
    print(f".env: {env_ok} ({env_path})")

    try:
        from mango.config import Config
        from mango.logging_setup import mask_secret

        cfg = Config.load()
    except RuntimeError as exc:
        print(f"\nConfig error: {exc}", file=sys.stderr)
        print(
            "\nTip: for a fully local LLM, install Ollama (https://ollama.com) and set "
            "MANGO_LLM_PROVIDER=ollama plus MANGO_OLLAMA_MODEL in .env.",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(f"\nUnexpected error loading config: {exc}", file=sys.stderr)
        return 1

    readiness: dict[str, str] = {
        "config": "ok",
        "microphone": "unknown",
        "llm_provider": "n/a",
        "tts_provider": "n/a",
    }

    print(f"\nLLM provider: {cfg.llm_provider}")
    if cfg.llm_provider == "groq":
        print(f"  Groq model: {cfg.groq_model}")
        print(f"  GROQ_API_KEY: {mask_secret(cfg.groq_api_key)}")
    else:
        print(f"  Ollama base: {cfg.ollama_base_url}")
        print(f"  Ollama model: {cfg.ollama_model}")
        if cfg.groq_api_key:
            print(f"  (unused) GROQ_API_KEY: {mask_secret(cfg.groq_api_key)}")

    _discord_t = (
        os.getenv("MANGO_DISCORD_BOT_TOKEN", "").strip()
        or os.getenv("DISCORD_BOT_TOKEN", "").strip()
    )
    if _discord_t:
        print(f"\nDiscord voice user token: {mask_secret(_discord_t)}")
    else:
        print(
            "\nDiscord voice user token: unset "
            "(set MANGO_DISCORD_BOT_TOKEN to a **user account** token for `python -m mango --discord-voice`; "
            "the bridge now uses discord.py-self — automating user accounts violates Discord ToS, use a throwaway).",
        )

    _dv_ctrl = os.getenv("MANGO_DISCORD_CONTROL_SECRET", "").strip()
    if _dv_ctrl:
        print(f"Discord voice control secret: {mask_secret(_dv_ctrl)}")
    else:
        print(
            "Discord voice control secret: unset (localhost `discord_voice` works without it; set secret to require header)",
        )
    _owner = os.getenv("MANGO_DISCORD_OWNER_USER_ID", "").strip()
    print(
        f"MANGO_DISCORD_OWNER_USER_ID: {_owner or '(unset — defaults to the selfbot account itself)'}",
    )

    print(f"\nWhisper model: {cfg.whisper_model}")
    print(f"TTS provider: {cfg.tts_provider}")
    _auto_bridge = os.getenv("MANGO_DISCORD_AUTO_START_BRIDGE", "").strip().lower()
    if _auto_bridge in ("0", "false", "no", "off"):
        _bridge_auto = "off"
    elif _auto_bridge in ("1", "true", "yes", "on"):
        _bridge_auto = "on"
    else:
        _bridge_auto = "on (default when MANGO_DESKTOP=1)"
    print(
        f"Discord bridge auto-start (MANGO_DISCORD_AUTO_START_BRIDGE): {_bridge_auto}  "
        "(discord_voice tool and Mango app can spawn `python -m mango --discord-voice`)",
    )
    print(
        f"TTS playback (MANGO_TTS_PLAYBACK): {cfg.tts_playback}  "
        "(discord = replies go to Discord voice only; bridge must be running or auto-started)",
    )
    print(f"Conversation history cap (non-system msgs): {cfg.max_conversation_messages}")
    print(f"Memory tier (MANGO_MEMORY_TIER): {cfg.memory_tier}")
    _tier_blurb = {
        "session": "in-RAM only — nothing saved after quit (default, most private)",
        "day": "plaintext JSON on disk — rolling ~1 day across restarts",
        "profile": "plaintext JSON on disk — long-lived merge across restarts",
    }
    print(f"  → {_tier_blurb.get(cfg.memory_tier, 'custom')}")
    print(
        f"Persistent memory flag: {'on' if cfg.persistent_memory else 'off'}  "
        f"dir={cfg.memory_dir}  floor={cfg.memory_max_messages}  "
        f"merge_days={cfg.memory_merge_days}  snapshots={cfg.memory_daily_snapshots}",
    )
    print("  See docs/memory-tiers.md for when to use session vs day vs profile.")
    hk_disp = "+".join(
        p.strip().upper() for p in cfg.hotkey.split("+") if p.strip()
    )
    print(f"Honorific (MANGO_HONORIFIC): {cfg.honorific or 'default (sir only, no maam)'}")

    print(f"\nPush-to-talk (HOTKEY): {hk_disp}")
    if sys.platform == "win32":
        try:
            import ctypes

            admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            admin = False
        if not admin:
            print(
                "  Tip: run PowerShell as Administrator if HOTKEY does nothing outside this window.",
            )
    print(f"Wake word (MANGO_WAKEWORD): {'on' if cfg.wake_word_enabled else 'off'}")
    print(
        f"  Phrase: {cfg.wake_phrase!r}  engine={cfg.wake_engine}  "
        f"openWakeWord={cfg.wake_use_openwakeword}  oww_models={','.join(cfg.oww_model_names) or '(none)'}  "
        f"oww_hybrid={cfg.wake_oww_whisper_confirm}  streaming={cfg.wake_streaming}  "
        f"interval={cfg.wake_interval_seconds}s  wake_whisper={cfg.wake_whisper_model or '(main model)'}",
    )
    print(
        f"Listen chime: wake={cfg.listen_chime_wake}  ptt={cfg.listen_chime_ptt}",
    )
    print(f"Always-listen energy VAD (MANGO_ALWAYS_LISTEN): {cfg.always_listen}")
    print(
        f"Always-listen VAD prefix gate: require={cfg.always_listen_require_transcript_prefix}  "
        f"prefixes={list(cfg.always_listen_transcript_prefixes)!r} (MANGO_ALWAYS_LISTEN_PREFIX comma-separated)",
    )
    print(f"Quiet hours: {cfg.quiet_hours!r}  tz={cfg.quiet_timezone!r}")
    print(f"Tool output cap: {cfg.max_tool_output_chars} chars")
    print(f"Streaming TTS: {cfg.streaming_tts}  speak_on_error: {cfg.speak_on_error}")
    print(
        "Tool confirmations: "
        f"powershell={cfg.require_powershell_confirmation} "
        f"phone={cfg.require_phone_confirmation} "
        f"xbox_turn_off={cfg.require_xbox_turn_off_confirmation}",
    )
    if cfg.disabled_tools:
        print(
            "Disabled tools (MANGO_DISABLED_TOOLS): "
            + ", ".join(sorted(cfg.disabled_tools)),
        )
    else:
        print(
            "Disabled tools: none (set MANGO_DISABLED_TOOLS=discord_voice,... to hide unused integrations)",
        )
    print(
        "Clipboard intent gate (MANGO_CLIPBOARD_REQUIRE_INTENT): "
        + (
            "on — read_clipboard only when utterance sounds clipboard-related"
            if cfg.clipboard_require_intent
            else "off — read_clipboard allowed any time the model calls it"
        ),
    )
    print(
        "Discord intent hints (MANGO_DISCORD_STRICT_INTENTS): "
        + (
            "on — music / ping / join-other require matching user phrasing"
            if not cfg.discord_relax_intent_gates
            else "off — host does not block discord_voice for missing music/ping/join phrasing"
        ),
    )
    print(f"\nPreset (MANGO_PRESET): {cfg.preset}")
    if cfg.preset in known_presets() and PRESET_PROMPT_SUFFIX.get(cfg.preset):
        print("  (This preset appends a short behavior hint to the system prompt.)")
    print(f"Personal skills dir: {cfg.skills_dir}")
    print(f"Skills char budget: {cfg.skills_max_chars}")
    if cfg.skills_dir.is_dir():
        md_files = sorted(cfg.skills_dir.glob("*.md"))
        print(f"  Found {len(md_files)} markdown file(s).")
        for p in md_files[:12]:
            print(f"    - {p.name}")
        if len(md_files) > 12:
            print(f"    … and {len(md_files) - 12} more")
    else:
        print(
            "  (Folder missing — create it and add *.md notes Mango should follow; "
            "see .env.example.)",
        )

    try:
        du = shutil.disk_usage(Path.home())
        free_gb = du.free / (1024**3)
        print(f"\nDisk free (user profile volume): {free_gb:.1f} GB")
    except OSError as exc:
        print(f"\nCould not read disk usage: {exc}", file=sys.stderr)

    try:
        import sounddevice as sd

        mic = sd.query_devices(kind="input")
        print(f"\nDefault input device: {mic['name']}")
        devs = sd.query_devices()
        n_in = sum(
            1 for d in devs if isinstance(d, dict) and int(d.get("max_input_channels") or 0) > 0
        )
        print(f"  Devices with inputs: {n_in}")
        readiness["microphone"] = "ok" if n_in > 0 else "warn"
    except Exception as exc:
        print(f"\nMicrophone listing failed: {exc}", file=sys.stderr)
        readiness["microphone"] = "warn"

    if cfg.llm_provider == "groq" and cfg.groq_api_key:
        readiness["llm_provider"] = "warn"
        try:
            import httpx

            r = httpx.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {cfg.groq_api_key}"},
                timeout=12.0,
            )
            print(f"\nGroq API models endpoint: HTTP {r.status_code}")
            if r.is_error:
                print(f"  Body: {(r.text or '')[:240]}", file=sys.stderr)
            else:
                readiness["llm_provider"] = "ok"
                try:
                    payload = r.json()
                    model_ids = [
                        str(m.get("id", ""))
                        for m in (payload.get("data") or [])
                        if isinstance(m, dict) and m.get("id")
                    ]
                    want = cfg.groq_model.strip()
                    if want and model_ids and want not in model_ids:
                        print(
                            f"  WARN: GROQ_MODEL={want!r} not in your account model list.",
                            file=sys.stderr,
                        )
                        alts = [m for m in model_ids if "llama" in m.lower()][:5]
                        if alts:
                            print(f"  Try one of: {', '.join(alts)}", file=sys.stderr)
                    elif want:
                        print(f"  GROQ_MODEL={want!r} is available on this key.")
                except Exception:
                    pass
        except Exception as exc:
            print(f"\nGroq connectivity check failed: {exc}", file=sys.stderr)
    elif cfg.llm_provider == "groq":
        readiness["llm_provider"] = "warn"

    if cfg.tts_provider == "elevenlabs" and cfg.elevenlabs_api_key:
        readiness["tts_provider"] = "warn"
        try:
            import httpx

            base = cfg.elevenlabs_api_base.rstrip("/")
            r = httpx.get(
                f"{base}/v1/user",
                headers={"xi-api-key": cfg.elevenlabs_api_key},
                timeout=12.0,
            )
            print(f"\nElevenLabs /v1/user: HTTP {r.status_code}")
            if not r.is_error:
                readiness["tts_provider"] = "ok"
        except Exception as exc:
            print(f"\nElevenLabs probe failed: {exc}", file=sys.stderr)
    elif cfg.tts_provider == "elevenlabs":
        readiness["tts_provider"] = "warn"
    else:
        readiness["tts_provider"] = "ok"

    if cfg.llm_provider == "ollama":
        readiness["llm_provider"] = "warn"
        try:
            import httpx

            tags_url = f"{cfg.ollama_base_url.rstrip('/')}/api/tags"
            r = httpx.get(tags_url, timeout=5.0)
            r.raise_for_status()
            data = r.json()
            names = [
                m.get("name", "")
                for m in (data.get("models") or [])
                if isinstance(m, dict)
            ]
            print(f"\nOllama reachable at {tags_url} ({len(names)} model(s) pulled).")
            want = cfg.ollama_model.strip()
            if want and not any(
                n == want or n.startswith(want + ":") for n in names if n
            ):
                print(
                    f"  Note: `{want}` not listed — run `ollama pull {want}` if chat fails.",
                )
            readiness["llm_provider"] = "ok"
        except Exception as exc:
            print(f"\nOllama probe failed: {exc}", file=sys.stderr)
            print(
                "  Ensure Ollama is running and OLLAMA_HOST / MANGO_OLLAMA_BASE_URL match.",
                file=sys.stderr,
            )

    def _state_label(state: str) -> str:
        if state == "ok":
            return "OK"
        if state == "warn":
            return "WARN"
        return "N/A"

    print("\nIntegration readiness:")
    print(f"  - Config load: {_state_label(readiness['config'])}")
    print(f"  - Microphone: {_state_label(readiness['microphone'])}")
    print(f"  - LLM provider ({cfg.llm_provider}): {_state_label(readiness['llm_provider'])}")
    print(f"  - TTS provider ({cfg.tts_provider}): {_state_label(readiness['tts_provider'])}")

    print("\nDoctor finished.")
    return 0

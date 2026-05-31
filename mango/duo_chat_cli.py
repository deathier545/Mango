"""Alternating Mango ↔ Amber dialogue for Electron duo mode."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load .env and SDL driver before pygame/SDL initializes (via mango.audio import).
_ENV_BOOT = Path(__file__).resolve().parent.parent / ".env"
if _ENV_BOOT.is_file():
    load_dotenv(dotenv_path=_ENV_BOOT, override=False, encoding="utf-8-sig")

if sys.platform == "win32":
    _sdl = (os.getenv("MANGO_SDL_AUDIODRIVER") or "directsound").strip() or "directsound"
    os.environ.setdefault("SDL_AUDIODRIVER", _sdl)

from groq import BadRequestError

from mango.audio import init_voice_mixer
from mango.config import Config
from mango.desktop_events import emit_desktop_event
from mango.duo_prompt import build_amber_duo_prompt, build_mango_duo_prompt
from mango.llm import GroqLLM, OllamaLLM
from mango.logging_setup import setup_logging
from mango.tool_recovery import strip_pseudo_tool_markup_for_speech
from mango.tts import EdgeTTS

logger = logging.getLogger(__name__)

AMBER_EDGE_VOICE = "en-US-AriaNeural"
MAX_TOPIC_CHARS = 300
MAX_LINE_CHARS = 700


def _result(payload: dict[str, Any]) -> None:
    print(f"MANGO_DUO_RESULT: {json.dumps(payload, ensure_ascii=True)}", flush=True)


def _emit_phase(speaker: str, phase: str, text: str = "") -> None:
    emit_desktop_event(
        {
            "type": "duo_phase",
            "speaker": speaker,
            "phase": phase,
            "text": text[:2000],
        }
    )


def _emit_done(*, ok: bool, lines: list[dict[str, str]], error: str = "") -> None:
    emit_desktop_event(
        {
            "type": "duo_done",
            "ok": ok,
            "lines": lines,
            "error": error[:500] if error else "",
        }
    )


def _clean_line(text: str, max_chars: int = MAX_LINE_CHARS) -> str:
    cleaned = strip_pseudo_tool_markup_for_speech(str(text or "").strip())
    if len(cleaned) <= max_chars:
        return cleaned or "…"
    return cleaned[: max_chars - 1].rstrip() + "…"


def _duo_context(lines: list[dict[str, str]], max_lines: int = 8) -> str:
    recent = lines[-max_lines:]
    return "\n".join(f"{row['speaker'].title()}: {row['text']}" for row in recent)


def _llm_reply(llm: GroqLLM | OllamaLLM, messages: list[dict[str, str]]) -> str:
    try:
        raw = llm.chat(messages)
    except BadRequestError as exc:
        logger.error("Duo turn rejected by provider: %s", exc)
        return "I'm having trouble responding right now."
    return _clean_line(raw)


def _speak_line(cfg: Config, *, voice: str, text: str, speaker: str) -> bool:
    if not text.strip():
        return True
    init_voice_mixer()
    tts = EdgeTTS(
        voice=voice,
        rate=cfg.edge_rate,
        pitch=cfg.edge_pitch,
        volume=cfg.edge_volume,
    )
    # Show transcript/orb immediately; audio may start slightly later.
    _emit_phase(speaker, "speaking", text)
    try:
        tts.speak(
            text,
            interrupt_check=None,
            streaming=cfg.streaming_tts,
            hud_level_out=None,
            on_playback_start=None,
        )
        return True
    except Exception:
        logger.exception("Duo TTS failed for %s", speaker)
        emit_desktop_event(
            {
                "type": "duo_phase",
                "speaker": speaker,
                "phase": "tts_error",
                "text": "Voice playback failed — check logs or try text-only mode.",
            }
        )
        return False


def _announce_line(*, speaker: str, text: str, speak: bool, cfg: Config, voice: str) -> None:
    if speak:
        _speak_line(cfg, voice=voice, text=text, speaker=speaker)
    else:
        _emit_phase(speaker, "speaking", text)
        time.sleep(0.85)
    _emit_phase(speaker, "idle", text)


def main() -> None:
    setup_logging()
    lines: list[dict[str, str]] = []
    try:
        raw = sys.stdin.read().strip()
        req = json.loads(raw) if raw else {}
        topic = str(req.get("topic") or "").strip()[:MAX_TOPIC_CHARS]
        if not topic:
            _result({"ok": False, "error": "Empty topic."})
            return
        rounds = int(req.get("rounds") or 2)
        rounds = max(1, min(6, rounds))
        speak = bool(req.get("speak", True))

        cfg = Config.load()
        if cfg.llm_provider == "ollama":
            llm: GroqLLM | OllamaLLM = OllamaLLM(
                base_url=cfg.ollama_base_url,
                model=cfg.ollama_model,
                timeout_seconds=cfg.ollama_timeout_s,
            )
        else:
            llm = GroqLLM(
                api_key=cfg.groq_api_key,
                model=cfg.groq_model,
                timeout_seconds=cfg.groq_timeout_s,
            )

        mango_prompt = build_mango_duo_prompt(topic=topic)
        amber_prompt = build_amber_duo_prompt(topic=topic)

        for round_idx in range(rounds):
            context = _duo_context(lines)
            _emit_phase("mango", "thinking")
            if round_idx == 0:
                user_msg = (
                    f"Topic: {topic}\n\n"
                    "You speak first. Open the panel conversation with a short take."
                )
            else:
                user_msg = (
                    f"Topic: {topic}\n\n"
                    f"Conversation so far:\n{context}\n\n"
                    "Mango, give the next short response."
                )
            mango_text = _llm_reply(
                llm,
                [
                    {"role": "system", "content": mango_prompt},
                    {"role": "user", "content": user_msg},
                ],
            )
            lines.append({"speaker": "mango", "text": mango_text})
            logger.info("Duo Mango: %s", mango_text)
            _announce_line(
                speaker="mango",
                text=mango_text,
                speak=speak,
                cfg=cfg,
                voice=cfg.edge_voice,
            )

            context = _duo_context(lines)
            _emit_phase("amber", "thinking")
            amber_user = (
                f"Topic: {topic}\n\n"
                f"Conversation so far:\n{context}\n\n"
                "Amber, give the next short response."
            )
            amber_text = _llm_reply(
                llm,
                [
                    {"role": "system", "content": amber_prompt},
                    {"role": "user", "content": amber_user},
                ],
            )
            lines.append({"speaker": "amber", "text": amber_text})
            logger.info("Duo Amber: %s", amber_text)
            _announce_line(
                speaker="amber",
                text=amber_text,
                speak=speak,
                cfg=cfg,
                voice=AMBER_EDGE_VOICE,
            )

        _emit_phase("mango", "idle")
        _emit_phase("amber", "idle")
        _emit_done(ok=True, lines=lines)
        _result({"ok": True, "lines": lines, "topic": topic, "rounds": rounds})
    except Exception as exc:
        logger.exception("Duo chat failed")
        _emit_phase("mango", "idle")
        _emit_phase("amber", "idle")
        _emit_done(ok=False, lines=lines, error=str(exc))
        _result({"ok": False, "error": str(exc), "lines": lines})


if __name__ == "__main__":
    main()

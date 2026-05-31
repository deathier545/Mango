"""One-shot text turn bridge for Electron manual chat."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from mango.audio import init_voice_mixer
from mango.config import Config
from mango.integrations.spotify.spotify_volume_duck import duck_spotify_session
from groq import BadRequestError

from mango.llm import GroqLLM, OllamaLLM
from mango.llm_tool_loop import _empty_reply_fallback, speaking_reply
from mango.tool_recovery import strip_pseudo_tool_markup_for_speech
from mango.logging_setup import setup_logging
from mango.tool_registry import ToolRegistry
from mango.tts import make_tts
from mango.voice_prompt import _build_system_prompt, refresh_system_message

logger = logging.getLogger(__name__)


def _normalize_history(raw: Any, limit: int = 20) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    prev: tuple[str, str] | None = None
    if not isinstance(raw, list):
        return out
    for item in raw[-limit:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        if role not in {"user", "assistant"}:
            continue
        text = " ".join(str(item.get("text") or item.get("content") or "").split())
        if not text:
            continue
        key = (role, text)
        if key == prev:
            continue
        out.append({"role": role, "content": text})
        prev = key
    return out


def _result(payload: dict[str, Any]) -> None:
    print(f"MANGO_TEXT_RESULT: {json.dumps(payload, ensure_ascii=True)}", flush=True)


def main() -> None:
    env_boot = Path(__file__).resolve().parent.parent / ".env"
    if env_boot.is_file():
        load_dotenv(dotenv_path=env_boot, override=False, encoding="utf-8-sig")
    setup_logging()
    try:
        raw = sys.stdin.read().strip()
        req = json.loads(raw) if raw else {}
        user_text = str(req.get("text") or "").strip()
        if not user_text:
            _result({"ok": False, "error": "Empty message."})
            return

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

        registry = ToolRegistry(cfg)
        messages: list[dict[str, Any]] = [{"role": "system", "content": _build_system_prompt(cfg)}]
        messages.extend(_normalize_history(req.get("history")))
        messages.append({"role": "user", "content": user_text})
        refresh_system_message(messages, cfg)
        registry.try_arm_powershell_from_user(user_text)
        with duck_spotify_session():
            llm_stats: dict[str, int] = {}
            try:
                reply = speaking_reply(
                    llm,
                    registry,
                    messages,
                    max_tool_rounds=cfg.max_llm_tool_rounds,
                    stats_out=llm_stats,
                )
            except BadRequestError as exc:
                logger.error("Groq rejected manual text turn (400): %s", exc)
                reply = _empty_reply_fallback(user_text)
            reply_text = strip_pseudo_tool_markup_for_speech(str(reply or "").strip())
            if not reply_text:
                reply_text = _empty_reply_fallback(user_text)
            logger.info("Manual text turn llm_stats=%s", llm_stats)
            speak = bool(req.get("speak", True))
            spoken = False
            speak_error = ""
            if speak and reply_text:
                try:
                    init_voice_mixer()
                    tts = make_tts(cfg)

                    def _on_playback_start() -> None:
                        logger.info("MANGO_STATE: speaking")

                    tts.speak(
                        reply_text,
                        interrupt_check=None,
                        streaming=cfg.streaming_tts,
                        hud_level_out=None,
                        on_playback_start=_on_playback_start,
                    )
                    logger.info("MANGO_STATE: listening")
                    spoken = True
                except Exception as exc:
                    logger.exception("Manual chat TTS failed")
                    logger.info("MANGO_STATE: error")
                    speak_error = str(exc)
        _result({"ok": True, "reply": reply_text, "spoken": spoken, "speak_error": speak_error})
    except Exception as exc:
        logger.exception("Manual text turn failed")
        _result({"ok": False, "error": str(exc)})


if __name__ == "__main__":
    main()

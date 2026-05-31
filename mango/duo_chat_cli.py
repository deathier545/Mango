"""Alternating Mango ↔ Amber dialogue for Electron duo mode."""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
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


def _llm_reply(llm: GroqLLM | OllamaLLM, messages: list[dict[str, str]]) -> str:
    try:
        raw = llm.chat(messages)
    except BadRequestError as exc:
        logger.error("Duo turn rejected by provider: %s", exc)
        return "I'm having trouble responding right now."
    text = strip_pseudo_tool_markup_for_speech(str(raw or "").strip())
    return text or "…"


def _speak_line(cfg: Config, *, voice: str, text: str, speaker: str) -> None:
    if not text.strip():
        return
    init_voice_mixer()
    tts = EdgeTTS(
        voice=voice,
        rate=cfg.edge_rate,
        pitch=cfg.edge_pitch,
        volume=cfg.edge_volume,
    )

    def _on_start() -> None:
        _emit_phase(speaker, "speaking", text)

    _emit_phase(speaker, "speaking", text)
    tts.speak(
        text,
        interrupt_check=None,
        streaming=cfg.streaming_tts,
        hud_level_out=None,
        on_playback_start=_on_start,
    )


def main() -> None:
    env_boot = Path(__file__).resolve().parent.parent / ".env"
    if env_boot.is_file():
        load_dotenv(dotenv_path=env_boot, override=False, encoding="utf-8-sig")
    setup_logging()
    try:
        raw = sys.stdin.read().strip()
        req = json.loads(raw) if raw else {}
        topic = str(req.get("topic") or "").strip()
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

        mango_prompt = build_mango_duo_prompt(cfg, topic=topic)
        amber_prompt = build_amber_duo_prompt(topic=topic)
        lines: list[dict[str, str]] = []
        last_mango = ""
        last_amber = ""

        for round_idx in range(rounds):
            # --- Mango turn ---
            _emit_phase("mango", "thinking")
            if round_idx == 0:
                user_msg = f"The user wants you and Amber to discuss: {topic}. You speak first — open the conversation."
            else:
                user_msg = f"Amber just said: {last_amber!r}. Your follow-up (stay on topic: {topic}):"
            mango_messages = [
                {"role": "system", "content": mango_prompt},
                {"role": "user", "content": user_msg},
            ]
            mango_text = _llm_reply(llm, mango_messages)
            last_mango = mango_text
            lines.append({"speaker": "mango", "text": mango_text})
            logger.info("Duo Mango: %s", mango_text)
            if speak:
                _speak_line(cfg, voice=cfg.edge_voice, text=mango_text, speaker="mango")
            else:
                _emit_phase("mango", "speaking", mango_text)
                time.sleep(0.85)
            _emit_phase("mango", "idle", mango_text)

            # --- Amber turn ---
            _emit_phase("amber", "thinking")
            amber_user = (
                f"Mango just said: {last_mango!r}. Respond as Amber. Topic: {topic}."
            )
            amber_messages = [
                {"role": "system", "content": amber_prompt},
                {"role": "user", "content": amber_user},
            ]
            amber_text = _llm_reply(llm, amber_messages)
            last_amber = amber_text
            lines.append({"speaker": "amber", "text": amber_text})
            logger.info("Duo Amber: %s", amber_text)
            if speak:
                _speak_line(cfg, voice=AMBER_EDGE_VOICE, text=amber_text, speaker="amber")
            else:
                _emit_phase("amber", "speaking", amber_text)
                time.sleep(0.85)
            _emit_phase("amber", "idle", amber_text)

        _emit_phase("mango", "idle")
        _emit_phase("amber", "idle")
        _result({"ok": True, "lines": lines, "topic": topic, "rounds": rounds})
    except Exception as exc:
        logger.exception("Duo chat failed")
        _emit_phase("mango", "idle")
        _emit_phase("amber", "idle")
        _result({"ok": False, "error": str(exc)})


if __name__ == "__main__":
    main()

from __future__ import annotations

import threading

import numpy as np

from mango.config import Config
from mango.turn_engine import TurnOutcome, run_turn


class _FakeStt:
    def __init__(self, text: str) -> None:
        self._text = text

    def transcribe(self, _audio: np.ndarray, _rate: int) -> str:
        return self._text


class _FakeRegistry:
    def __init__(self) -> None:
        self.armed: list[str] = []

    def try_arm_powershell_from_user(self, text: str) -> None:
        self.armed.append(text)


def test_turn_engine_end_to_end_invokes_stt_llm_tts_and_persists():
    cfg = Config(sample_rate=16000, min_record_seconds=0.1)
    stt = _FakeStt("hey mango test")
    registry = _FakeRegistry()
    messages: list[dict] = [{"role": "system", "content": "sys"}]
    states: list[str] = []
    spoken: list[str] = []
    persisted = {"n": 0}
    emitted: list[tuple[str, dict]] = []

    def _set_state(s: str) -> None:
        states.append(s)

    def _speak_reply(_cfg, _tts, reply: str, **_kwargs) -> bool:
        spoken.append(reply)
        on_playback_start = _kwargs.get("on_playback_start")
        if callable(on_playback_start):
            on_playback_start()
        return False

    def _speaking_reply(_llm, _registry, _messages, *, max_tool_rounds: int, stats_out=None, **kwargs) -> str:
        assert max_tool_rounds == cfg.max_llm_tool_rounds
        if isinstance(stats_out, dict):
            stats_out.update(
                {
                    "llm_calls": 2,
                    "tool_calls_executed": 1,
                    "rounds_with_tool_calls": 1,
                    "total_steps": 1,
                }
            )
        return "done"

    def _persist() -> None:
        persisted["n"] += 1

    wake_suppress = threading.Event()
    wake_lock = threading.Lock()
    wake_depth = [0]
    audio = np.ones((int(cfg.sample_rate * 0.2),), dtype=np.float32) * 0.05

    from mango import turn_engine as te

    original_emit = te.emit_metric
    te.emit_metric = lambda event, **fields: emitted.append((event, fields))
    try:
        outcome = run_turn(
            audio=audio,
            source="ptt",
            cfg=cfg,
            stt=stt,
            llm=object(),
            registry=registry,
            messages=messages,
            tts=object(),
            hud_level=None,
            wake_suppress=wake_suppress,
            wake_turn_lock=wake_lock,
            wake_turn_depth=wake_depth,
            set_assistant_state=_set_state,
            barge_check=lambda: False,
            speak_reply=_speak_reply,
            speaking_reply=_speaking_reply,
            persist_memory=_persist,
        )
    finally:
        te.emit_metric = original_emit

    assert isinstance(outcome, TurnOutcome)
    assert outcome.reply == "done"
    assert outcome.interrupted is False
    assert "thinking" in states
    assert "speaking" in states
    assert spoken == ["done"]
    assert persisted["n"] == 1
    assert registry.armed == ["hey mango test"]
    assert messages[-1]["role"] == "user"
    llm_metric = [fields for event, fields in emitted if event == "turn_llm_done"][0]
    assert llm_metric["llm_calls"] == 2
    assert llm_metric["tool_calls_executed"] == 1
    assert llm_metric["rounds_with_tool_calls"] == 1
    # Wake unsuppress runs on a background thread; avoid timing-sensitive assertions here.


def test_turn_engine_clips_long_spoken_reply_for_tts():
    cfg = Config(sample_rate=16000, min_record_seconds=0.1, max_spoken_reply_chars=90)
    stt = _FakeStt("hello there")
    registry = _FakeRegistry()
    messages: list[dict] = [{"role": "system", "content": "sys"}]
    spoken: list[str] = []

    def _set_state(_s: str) -> None:
        return None

    def _speak_reply(_cfg, _tts, reply: str, **_kwargs) -> bool:
        spoken.append(reply)
        return False

    long_reply = "The system check is complete. " + ("detail " * 100)

    def _speaking_reply(_llm, _registry, _messages, *, max_tool_rounds: int, stats_out=None, **kwargs) -> str:
        assert max_tool_rounds == cfg.max_llm_tool_rounds
        return long_reply

    outcome = run_turn(
        audio=np.ones((int(cfg.sample_rate * 0.2),), dtype=np.float32) * 0.05,
        source="ptt",
        cfg=cfg,
        stt=stt,
        llm=object(),
        registry=registry,
        messages=messages,
        tts=object(),
        hud_level=None,
        wake_suppress=threading.Event(),
        wake_turn_lock=threading.Lock(),
        wake_turn_depth=[0],
        set_assistant_state=_set_state,
        barge_check=lambda: False,
        speak_reply=_speak_reply,
        speaking_reply=_speaking_reply,
        persist_memory=lambda: None,
    )

    assert outcome.reply == long_reply
    assert len(spoken[0]) <= 90
    assert spoken[0].endswith("I can give more details if you want.")


def test_turn_engine_reports_tts_interrupt() -> None:
    cfg = Config(sample_rate=16000, min_record_seconds=0.1)
    stt = _FakeStt("stop mango")
    registry = _FakeRegistry()
    messages: list[dict] = [{"role": "system", "content": "sys"}]
    tts_phase = {"active": False}

    def _speak_reply(_cfg, _tts, reply: str, **_kwargs) -> bool:
        assert reply == "hello"
        return True

    def _speaking_reply(_llm, _registry, _messages, *, max_tool_rounds: int, stats_out=None, **kwargs) -> str:
        tts_phase["active"] = True
        return "hello"

    outcome = run_turn(
        audio=np.ones((int(cfg.sample_rate * 0.2),), dtype=np.float32) * 0.05,
        source="ptt",
        cfg=cfg,
        stt=stt,
        llm=object(),
        registry=registry,
        messages=messages,
        tts=object(),
        hud_level=None,
        wake_suppress=threading.Event(),
        wake_turn_lock=threading.Lock(),
        wake_turn_depth=[0],
        set_assistant_state=lambda _s: None,
        barge_check=lambda: tts_phase["active"],
        speak_reply=_speak_reply,
        speaking_reply=_speaking_reply,
        persist_memory=lambda: None,
    )
    assert outcome.reply == "hello"
    assert outcome.interrupted is True

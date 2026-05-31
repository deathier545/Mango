from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import time

from mango.tts import EdgeTTS, _wait_future


def test_wait_future_cancels_on_interrupt() -> None:
    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(time.sleep, 0.5)
        out = _wait_future(fut, lambda: True, poll_s=0.02)
    assert out is None


def test_edge_tts_streaming_threshold_avoids_chunking_for_short_text(monkeypatch):
    calls: list[bytes] = []

    async def _fake_synth(self, text: str) -> bytes:
        return text.encode("utf-8")

    def _fake_play(data: bytes, **_kwargs) -> bool:
        calls.append(data)
        return False

    monkeypatch.setattr(EdgeTTS, "_synthesize", _fake_synth)
    monkeypatch.setattr("mango.tts.play_mp3_bytes", _fake_play)

    text = "x" * 170  # below streaming threshold (>180)
    EdgeTTS().speak(text, streaming=True)
    assert len(calls) == 1


def test_edge_tts_interrupt_stops_after_first_chunk_playback(monkeypatch):
    played: list[bytes] = []

    async def _fake_synth(self, text: str) -> bytes:
        return text.encode("utf-8")

    def _fake_play(data: bytes, **_kwargs) -> bool:
        played.append(data)
        return True  # simulate barge-in during first chunk playback

    monkeypatch.setattr(EdgeTTS, "_synthesize", _fake_synth)
    monkeypatch.setattr("mango.tts.play_mp3_bytes", _fake_play)

    text = "a" * 800  # forces multiple chunks with current chunk size
    interrupted = EdgeTTS().speak(text, streaming=True)
    assert interrupted is True
    assert len(played) == 1

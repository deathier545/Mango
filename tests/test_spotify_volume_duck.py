"""spotify_volume_duck (no real WASAPI)."""

from __future__ import annotations

import sys
from unittest import mock

import pytest

import mango.integrations.spotify.spotify_volume_duck as svd


def test_ducking_disabled_non_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    assert svd.ducking_enabled() is False


def test_ducking_disabled_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("MANGO_SPOTIFY_DUCK", "0")
    assert svd.ducking_enabled() is False


def test_duck_volume_multiplier_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MANGO_SPOTIFY_DUCK_VOLUME", raising=False)
    assert svd._duck_volume_multiplier() == pytest.approx(0.12)


def test_duck_volume_multiplier_clamped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANGO_SPOTIFY_DUCK_VOLUME", "99")
    assert svd._duck_volume_multiplier() == 1.0
    monkeypatch.setenv("MANGO_SPOTIFY_DUCK_VOLUME", "0.001")
    assert svd._duck_volume_multiplier() == pytest.approx(0.02)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only env branch")
def test_duck_calls_discord_cable_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANGO_SPOTIFY_DUCK", "1")
    posts: list[str] = []

    class FakeResp:
        status_code = 200

    def fake_post(url: str, **kwargs: object) -> FakeResp:
        posts.append(url)
        return FakeResp()

    with mock.patch.object(svd, "_snapshot_and_duck", return_value=[]):
        with mock.patch("httpx.post", side_effect=fake_post):
            with svd.duck_spotify_session():
                pass
    assert any("/v1/voice/music/duck" in u for u in posts)
    assert any("/v1/voice/music/restore" in u for u in posts)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only env branch")
def test_duck_session_reentrant_single_restore(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANGO_SPOTIFY_DUCK", "1")
    sav = mock.Mock()
    sav.GetMasterVolume.return_value = 0.8
    sav.GetMute.return_value = 0
    fake_session = mock.Mock()
    fake_session.Process = mock.Mock()
    fake_session.Process.name.return_value = "Spotify.exe"
    fake_session.SimpleAudioVolume = sav

    with mock.patch.object(svd, "_collect_playback_sessions", return_value=[fake_session]):
        with svd.duck_spotify_session():
            with svd.duck_spotify_session():
                assert sav.SetMasterVolume.call_count >= 1
    assert sav.SetMasterVolume.call_count >= 2
    restores = [c for c in sav.SetMasterVolume.call_args_list if abs(float(c[0][0]) - 0.8) < 1e-9]
    assert len(restores) == 1, "nested duck should restore volume only once"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only env branch")
def test_duck_session_restores_on_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANGO_SPOTIFY_DUCK", "1")
    sav = mock.Mock()
    sav.GetMasterVolume.return_value = 0.8
    sav.GetMute.return_value = 0
    fake_session = mock.Mock()
    fake_session.Process = mock.Mock()
    fake_session.Process.name.return_value = "Spotify.exe"
    fake_session.SimpleAudioVolume = sav

    with mock.patch.object(svd, "_collect_playback_sessions", return_value=[fake_session]):
        with svd.duck_spotify_session():
            assert sav.SetMasterVolume.called
    restores = [c for c in sav.SetMasterVolume.call_args_list if abs(float(c[0][0]) - 0.8) < 1e-9]
    assert restores, "expected restore to prior master level"

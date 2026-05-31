"""spotify_transport and spotify_play helpers (no Spotify app required)."""

from __future__ import annotations

import sys
from unittest import mock

import pytest

from mango.tools import spotify_play as sp
from mango.tools.spotify_transport import run as transport_run


def test_spotify_transport_non_windows_message() -> None:
    if sys.platform == "win32":
        pytest.skip("non-Windows message")
    out = transport_run("next")
    assert "Windows media keys" in out or "Web API" in out


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
def test_spotify_transport_web_mode_uses_api(monkeypatch) -> None:
    monkeypatch.setenv("MANGO_SPOTIFY_WEB_PLAYBACK", "1")

    with (
        mock.patch("mango.integrations.spotify.spotify_user_auth.get_valid_access_token", return_value="tok"),
        mock.patch("mango.integrations.spotify.spotify_player_server.web_api_transport", return_value=(True, "OK")) as wapi,
        mock.patch("mango.tools.spotify_transport._tap_vk") as tap,
    ):
        out = transport_run("next")
    wapi.assert_called_once_with("tok", "next")
    tap.assert_not_called()
    assert "Web API" in out


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
def test_spotify_transport_next_taps_key(monkeypatch) -> None:
    monkeypatch.delenv("MANGO_SPOTIFY_WEB_PLAYBACK", raising=False)
    monkeypatch.setenv("MANGO_SPOTIFY_MINIMIZED", "0")
    with mock.patch("mango.tools.spotify_transport._tap_vk") as tap:
        out = transport_run("next")
    tap.assert_called_once()
    assert "Next" in out


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
def test_spotify_transport_minimized_runs_window_cycle(monkeypatch) -> None:
    monkeypatch.delenv("MANGO_SPOTIFY_WEB_PLAYBACK", raising=False)
    monkeypatch.setenv("MANGO_SPOTIFY_MINIMIZED", "1")
    with (
        mock.patch("mango.integrations.spotify.spotify_windows_ui.foreground_spotify_windows") as fg,
        mock.patch("mango.integrations.spotify.spotify_windows_ui.pause_then_minimize_spotify") as pm,
        mock.patch("mango.tools.spotify_transport._tap_vk"),
    ):
        transport_run("previous")
    fg.assert_called_once()
    pm.assert_called_once()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
def test_spotify_transport_unknown_action() -> None:
    with mock.patch("mango.tools.spotify_transport._tap_vk") as tap:
        out = transport_run("not_an_action")  # type: ignore[arg-type]
    tap.assert_not_called()
    assert "Unknown" in out


def test_spotify_exe_override(monkeypatch, tmp_path) -> None:
    fake = tmp_path / "Spotify.exe"
    fake.write_bytes(b"")
    monkeypatch.setenv("MANGO_SPOTIFY_EXE", str(fake))
    monkeypatch.setattr(sys, "platform", "win32")
    assert sp._spotify_exe_windows() == str(fake.resolve())


def test_spotify_exe_localappdata(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("MANGO_SPOTIFY_EXE", raising=False)
    root = tmp_path / "local" / "Spotify"
    root.mkdir(parents=True)
    exe = root / "Spotify.exe"
    exe.write_bytes(b"")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(sys, "platform", "win32")
    assert sp._spotify_exe_windows() == str(exe.resolve())

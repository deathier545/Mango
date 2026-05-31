"""spotify_desktop_api (no network — mocks)."""

from __future__ import annotations

from unittest import mock

import httpx
import pytest

import mango.integrations.spotify.spotify_desktop_api as sda


def test_pick_device_prefers_computer() -> None:
    devices = [
        {"id": "phone", "type": "Smartphone", "name": "Pixel", "is_restricted": False},
        {"id": "pc", "type": "Computer", "name": "DESKTOP-ABC", "is_restricted": False},
    ]
    assert sda.pick_device_id(devices) == "pc"


def test_pick_device_name_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANGO_SPOTIFY_DEVICE_NAME", "living room")
    devices = [
        {"id": "a", "type": "Speaker", "name": "Living Room", "is_restricted": False},
        {"id": "b", "type": "Computer", "name": "PC", "is_restricted": False},
    ]
    assert sda.pick_device_id(devices) == "a"


def test_play_track_uri_success(monkeypatch: pytest.MonkeyPatch) -> None:
    devs = [{"id": "dev1", "type": "Computer", "is_restricted": False, "is_active": True}]

    def fake_fetch(_access: str):
        return devs, None

    class OkResp:
        status_code = 204
        text = ""

    monkeypatch.setattr(sda, "fetch_devices", fake_fetch)
    with mock.patch.object(httpx, "put", return_value=OkResp()):
        ok, msg = sda.play_track_uri("tok", "spotify:track:abcXYZ:play")
    assert ok
    assert "Connect" in msg


def test_play_track_uri_rejects_non_track() -> None:
    ok, msg = sda.play_track_uri("tok", "spotify:album:abc")
    assert ok is False
    assert "spotify:track" in msg

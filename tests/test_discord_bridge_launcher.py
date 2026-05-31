"""Tests for Discord bridge auto-start helpers."""

from __future__ import annotations

import mango.integrations.discord.discord_bridge_launcher as launcher


def test_auto_start_enabled_desktop_default(monkeypatch):
    monkeypatch.delenv("MANGO_DISCORD_AUTO_START_BRIDGE", raising=False)
    monkeypatch.setenv("MANGO_DESKTOP", "1")
    assert launcher.auto_start_enabled() is True


def test_auto_start_disabled_explicit(monkeypatch):
    monkeypatch.setenv("MANGO_DISCORD_AUTO_START_BRIDGE", "0")
    monkeypatch.setenv("MANGO_DESKTOP", "1")
    assert launcher.auto_start_enabled() is False


def test_bridge_reachable_on_200(monkeypatch):
    class FakeResponse:
        status_code = 200

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, headers=None):
            return FakeResponse()

    monkeypatch.setattr(launcher.httpx, "Client", FakeClient)
    assert launcher.bridge_control_reachable() is True


def test_bridge_poll_interval_uses_faster_early_checks() -> None:
    assert launcher._poll_interval_for_elapsed(2.0, 0.0) == 0.5
    assert launcher._poll_interval_for_elapsed(1.0, 9.0) == 0.5
    assert launcher._poll_interval_for_elapsed(2.0, 12.0) == 2.0

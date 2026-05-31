from __future__ import annotations

from mango.config import Config
from mango.config_build import apply_safe_mode


def test_apply_safe_mode_disables_wake_and_tools() -> None:
    cfg = Config(
        wake_word_enabled=True,
        always_listen=True,
        safe_mode=True,
    )
    cfg.wake.enabled = True
    apply_safe_mode(cfg)
    assert cfg.wake_word_enabled is False
    assert cfg.always_listen is False
    assert cfg.wake.enabled is False
    assert "discord_voice" in cfg.disabled_tools
    assert "run_powershell" in cfg.disabled_tools


def test_apply_safe_mode_noop_when_off() -> None:
    cfg = Config(wake_word_enabled=True, always_listen=True, safe_mode=False)
    before = cfg.disabled_tools
    apply_safe_mode(cfg)
    assert cfg.wake_word_enabled is True
    assert cfg.always_listen is True
    assert cfg.disabled_tools == before

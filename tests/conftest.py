"""Pytest fixtures for Mango."""

from __future__ import annotations

import pytest


@pytest.fixture
def cfg_root(tmp_path, monkeypatch):
    """Isolate Config.load from project and cwd .env files."""
    import mango.config as mc

    monkeypatch.setattr(mc, "_PROJECT_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    # Empty project .env so load_dotenv does not walk up to the real repo .env.
    (tmp_path / ".env").write_text("", encoding="utf-8")
    return tmp_path

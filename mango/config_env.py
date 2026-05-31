"""Environment variable parsing helpers for Mango config."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

def _sanitize_api_key(raw: str) -> str:
    key = (raw or "").strip()
    if len(key) >= 2 and key[0] == key[-1] and key[0] in "\"'":
        key = key[1:-1].strip()
    return key


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid float %s=%r — using %s", name, raw, default)
        return default


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid int %s=%r — using %s", name, raw, default)
        return default


def _ollama_base_url_from_env() -> str:
    raw = (
        os.getenv("MANGO_OLLAMA_BASE_URL", "").strip()
        or os.getenv("OLLAMA_HOST", "").strip()
        or "http://127.0.0.1:11434"
    )
    if "://" not in raw:
        raw = f"http://{raw}"
    return raw.rstrip("/")

"""Backward-compatible re-exports; narration lives in ``tool_narration``."""

from __future__ import annotations

from mango.tool_narration import (
    extract_track_hint,
    short_completion_reply,
    speak_progress,
    suppress_tool_narration,
)

__all__ = [
    "extract_track_hint",
    "short_completion_reply",
    "speak_progress",
    "suppress_tool_narration",
]

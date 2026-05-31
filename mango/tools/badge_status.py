"""Progress badge snapshot for LLM and voice replies."""

from __future__ import annotations

from typing import Any

from mango.badges import format_badge_reply

DESCRIPTION = (
    "Return Mango's own badge progress: unlocked count, nearest goals, and hints. "
    "Call when the user asks about Mango's badges, his progress, unlocks, achievements, "
    "milestones, or what he should work on next."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


def run(**_: Any) -> str:
    from mango.badges import format_badge_reply

    return format_badge_reply("")

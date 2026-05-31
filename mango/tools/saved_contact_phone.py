"""Read-only: return a saved contact phone from ``MANGO_CONTACT_<SLUG>_PHONE`` (no outbound call)."""

from __future__ import annotations

import re
from typing import Any

from mango.tools.phone_call import _contact_phone, _english_join, _slug_display

_E164 = re.compile(r"^\+[1-9]\d{7,14}$")


def build_tool_spec(owner: str, slugs: tuple[str, ...]) -> tuple[str, dict[str, Any]]:
    labels = [_slug_display(s) for s in slugs]
    human = _english_join(labels)
    desc = (
        "Read the phone number stored on this PC for a saved contact (from .env: MANGO_CONTACT_<NAME>_PHONE). "
        f"Use when {owner} asks what {human}'s phone number is, to read digits from the saved list, "
        "or to look up a number without placing a call. "
        "Do not use web_search for these private saved numbers. "
        "Use phone_call only when they clearly ask you to call or dial someone."
    )
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "contact": {
                "type": "string",
                "enum": list(slugs),
                "description": "Which saved contact's number to read.",
            },
        },
        "required": ["contact"],
        "additionalProperties": False,
    }
    return desc, schema


def run(
    contact: str,
    *,
    _allowed_contacts: tuple[str, ...] | None = None,
) -> str:
    allowed = _allowed_contacts if _allowed_contacts else ("ariana", "brooke", "dylan")
    key = (contact or "").strip().casefold()
    if key not in allowed:
        human = _english_join([_slug_display(s) for s in allowed])
        return f"No saved contact {contact!r}. Configured slugs: {human}."
    display = _slug_display(key)
    raw = _contact_phone(key)
    if not raw:
        env_key = re.sub(r"[^A-Za-z0-9]+", "_", key).upper().strip("_")
        return (
            f"No phone number is saved for {display}. Set MANGO_CONTACT_{env_key}_PHONE=+1... in .env "
            "to add it to the list."
        )
    if not _E164.match(raw):
        return (
            f"A value is set for {display} ({raw!r}) but it is not valid E.164 (+country…). "
            "Fix the entry in .env so Mango can read it reliably."
        )
    return (
        f"Saved phone number for {display}: {raw}. "
        "Repeat this number clearly for voice (you may group digits naturally for speaking)."
    )

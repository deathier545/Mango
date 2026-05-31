"""Manage global memory cards (people, preferences, devices, facts)."""

from __future__ import annotations

from typing import Any

from mango.smart.smart_store import cards_for_prompt, delete_card, upsert_card

DESCRIPTION = (
    "Manage long-term memory cards the user can edit in the Smart tab. "
    "Use action list to read cards; add/update/delete when the user asks to remember something persistent."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["list", "add", "update", "delete"],
        },
        "card_id": {"type": "string", "description": "For update/delete."},
        "title": {"type": "string"},
        "content": {"type": "string"},
        "category": {
            "type": "string",
            "enum": ["person", "preference", "device", "fact", "task"],
            "description": "Card category (default fact).",
        },
    },
    "required": ["action"],
    "additionalProperties": False,
}


def run(
    action: str,
    *,
    card_id: str | None = None,
    title: str | None = None,
    content: str | None = None,
    category: str | None = None,
) -> str:
    act = (action or "").strip().lower()
    if act == "list":
        text = cards_for_prompt(40)
        return text or "No memory cards saved yet."
    if act == "add":
        if not (content or "").strip():
            return "memory_card add needs content."
        entry = upsert_card(
            title=title or "Note",
            content=content or "",
            category=category or "fact",
        )
        return f"Saved memory card {entry['id']}: {entry['title']}"
    if act == "update":
        if not card_id:
            return "memory_card update needs card_id."
        entry = upsert_card(
            card_id=card_id,
            title=title or "Note",
            content=content or "",
            category=category or "fact",
        )
        return f"Updated memory card {entry['id']}"
    if act == "delete":
        if not card_id:
            return "memory_card delete needs card_id."
        if delete_card(card_id):
            return f"Deleted memory card {card_id}"
        return f"No card with id {card_id}"
    return f"Unknown action {action!r}"

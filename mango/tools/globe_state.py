"""Control embedded globe visibility in desktop mode."""

from __future__ import annotations

from typing import Any

import mango.desktop.desktop_ipc as desktop_ipc

DESCRIPTION = (
    "Show or hide the embedded 3D globe UI. Use action=show when opening map/globe context, "
    "and action=hide when the user says return to normal or close the globe."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["show", "hide"],
            "description": "show = reveal globe background; hide = return to normal Mango ball mode.",
        }
    },
    "required": ["action"],
    "additionalProperties": False,
}


def run(action: str) -> str:
    a = (action or "").strip().casefold()
    if a not in {"show", "hide"}:
        return "Invalid action for globe_state; use show or hide."
    ok = desktop_ipc.try_set_globe_visible(a == "show")
    if not ok:
        return "Globe UI control unavailable outside desktop mode."
    if a == "show":
        return "Globe view activated."
    return "Returned to normal Mango view."

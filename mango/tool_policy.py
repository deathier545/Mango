"""Tool risk levels, intent hints, and confirmation policy helpers."""

from __future__ import annotations

from typing import Any

# Do not log text previews for tool outputs (privacy).
_SENSITIVE_TOOL_OUTPUTS = frozenset(
    {
        "read_clipboard",
        "search_files",
        "run_powershell",
        "web_search",
        "saved_contact_phone",
        "clipboard_write",
        "desktop_notify",
        "therapy_support",
        "product_research",
    }
)

_ERR_TOOL_BAD_ARGS = "ERR_TOOL_BAD_ARGS"
_ERR_TOOL_EXCEPTION = "ERR_TOOL_EXCEPTION"

_TOOL_RISK_LEVELS: dict[str, str] = {
    "run_powershell": "high",
    "phone_call": "high",
    "xbox_console": "high",
    "open_app": "medium",
    "close_app": "medium",
    "spotify_play": "medium",
    "spotify_transport": "medium",
    "spotify_session": "medium",
    "discord_voice": "medium",
    "read_clipboard": "medium",
    "clipboard_write": "medium",
    "clipboard_ai": "medium",
    "memory_card": "low",
    "run_routine": "medium",
    "daily_brief": "low",
    "badge_status": "low",
}

_TOOL_HANDOFF_DOMAIN: dict[str, str] = {
    "spotify_play": "music",
    "phone_call": "phone",
    "search_files": "research",
    "web_search": "research",
    "product_research": "research",
}

_CLIPBOARD_HINTS = (
    "clipboard",
    "copied",
    "paste",
    "clip board",
    "clip-board",
    "what i copied",
    "what's copied",
    "what is copied",
    "clipboard text",
    "on my clip",
)

_CONTACT_INFO_HINTS = (
    "phone",
    "phone number",
    "number",
    "digits",
    "contact",
    "reach",
    "what is",
    "what's",
    "give me",
)

_DISCORD_MUSIC_HINTS = (
    "music",
    "spotify",
    "song",
    "play ",
    "stream",
    "audio",
)

_DISCORD_PING_HINTS = (
    "ping",
    "notify",
    "message them",
    "tell them",
    "mention",
)

_DISCORD_JOIN_OTHER_HINTS = (
    "join any",
    "join another",
    "join available",
    "join someone",
    "join a call",
    "find a call",
)

_AFFIRM_MARKERS = (
    "confirm",
    "confirmed",
    "yes",
    "yeah",
    "yep",
    "sure",
    "approve",
    "approved",
    "go ahead",
    "please run",
    "ok run",
    "okay run",
    "do it",
    "run it",
    "approve shell",
    "sounds good",
    "that's fine",
    "thats fine",
)

_SHELL_APPROVAL_HINTS = (
    "shell",
    "powershell",
    "command",
)

_PHONE_APPROVAL_HINTS = (
    "call",
    "dial",
    "phone",
)

_XBOX_APPROVAL_HINTS = (
    "xbox",
    "turn off",
    "shutdown",
    "power off",
)


def risk_level(tool_name: str) -> str:
    return _TOOL_RISK_LEVELS.get(tool_name, "low")


def _last_user_text(msgs: list[dict[str, Any]] | None) -> str:
    if not msgs:
        return ""
    for m in reversed(msgs):
        if m.get("role") == "user":
            return str(m.get("content") or "").strip()
    return ""


def _clipboard_intent(user_text: str) -> bool:
    t = user_text.casefold()
    return any(h in t for h in _CLIPBOARD_HINTS)


def _contact_info_intent(user_text: str) -> bool:
    t = user_text.casefold()
    return any(h in t for h in _CONTACT_INFO_HINTS)


def _has_any_hint(user_text: str, hints: tuple[str, ...]) -> bool:
    t = user_text.casefold()
    return any(h in t for h in hints)


def _affirmative(user_text: str, *, tool_name: str | None = None) -> bool:
    t = user_text.strip().casefold()
    if len(t) > 200:
        t = t[:200]
    if tool_name == "run_powershell":
        if "approve" in t and any(h in t for h in _SHELL_APPROVAL_HINTS):
            return True
        if not any(h in t for h in _SHELL_APPROVAL_HINTS):
            return False
    elif tool_name == "phone_call":
        if "approve" in t and any(h in t for h in _PHONE_APPROVAL_HINTS):
            return True
        if not any(h in t for h in _PHONE_APPROVAL_HINTS):
            return False
    elif tool_name == "xbox_console":
        if "approve" in t and any(h in t for h in _XBOX_APPROVAL_HINTS):
            return True
        if not any(h in t for h in _XBOX_APPROVAL_HINTS):
            return False
    return any(m in t for m in _AFFIRM_MARKERS)

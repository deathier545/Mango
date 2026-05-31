"""OpenAI-style function tool JSON schemas for the Mango host."""

from __future__ import annotations

from typing import Any

from mango.config import Config
from mango.tools import (
    badge_status,
    clipboard_ai,
    clipboard_write,
    close_app,
    daily_brief,
    delay_timer,
    desktop_notify,
    discord_voice,
    globe_state,
    globe_view,
    memory_card,
    open_app,
    phone_call,
    product_research,
    read_clipboard,
    reminders,
    run_powershell,
    run_routine,
    saved_contact_phone,
    screenshot_desktop,
    search_files,
    spotify_play,
    spotify_session,
    spotify_transport,
    system_info,
    therapy_support,
    volume_control,
    web_search,
    xbox_console,
)


def _fn_tool(name: str, description: str, parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


def _tool_name(defn: dict[str, Any]) -> str:
    fn = defn.get("function") or {}
    return str(fn.get("name") or "")


def all_builtin_tool_names() -> frozenset[str]:
    """Every tool name the host may register (used for pseudo-syntax recovery)."""
    return frozenset(
        {
            "open_app",
            "close_app",
            "spotify_play",
            "spotify_transport",
            "spotify_session",
            "discord_voice",
            "globe_state",
            "globe_view",
            "search_files",
            "web_search",
            "therapy_support",
            "product_research",
            "system_info",
            "read_clipboard",
            "run_powershell",
            "saved_contact_phone",
            "phone_call",
            "reminders",
            "delay_timer",
            "desktop_notify",
            "volume_control",
            "screenshot_desktop",
            "clipboard_write",
            "xbox_console",
            "memory_card",
            "run_routine",
            "clipboard_ai",
            "daily_brief",
            "badge_status",
        }
    )


def build_tool_definitions(
    cfg: Config,
    owner_display_name: str,
    phone_contact_slugs: tuple[str, ...] | list[str],
    *,
    disabled_tools: frozenset[str] | None = None,
) -> list[dict[str, Any]]:
    _ = cfg
    slugs = tuple(phone_contact_slugs)
    disabled = disabled_tools or frozenset()
    defs = [
        _fn_tool("open_app", open_app.DESCRIPTION, open_app.SCHEMA),
        _fn_tool("close_app", close_app.DESCRIPTION, close_app.SCHEMA),
        _fn_tool("spotify_play", spotify_play.DESCRIPTION, spotify_play.SCHEMA),
        _fn_tool("spotify_transport", spotify_transport.DESCRIPTION, spotify_transport.SCHEMA),
        _fn_tool("spotify_session", spotify_session.DESCRIPTION, spotify_session.SCHEMA),
        _fn_tool(
            "discord_voice",
            discord_voice.description_for(owner_display_name),
            discord_voice.SCHEMA,
        ),
        _fn_tool("globe_state", globe_state.DESCRIPTION, globe_state.SCHEMA),
        _fn_tool("globe_view", globe_view.DESCRIPTION, globe_view.SCHEMA),
        _fn_tool("search_files", search_files.DESCRIPTION, search_files.SCHEMA),
        _fn_tool("web_search", web_search.DESCRIPTION, web_search.SCHEMA),
        _fn_tool("therapy_support", therapy_support.DESCRIPTION, therapy_support.SCHEMA),
        _fn_tool("product_research", product_research.DESCRIPTION, product_research.SCHEMA),
        _fn_tool("system_info", system_info.DESCRIPTION, system_info.SCHEMA),
        _fn_tool("read_clipboard", read_clipboard.DESCRIPTION, read_clipboard.SCHEMA),
        _fn_tool("run_powershell", run_powershell.DESCRIPTION, run_powershell.SCHEMA),
        _fn_tool(
            "saved_contact_phone",
            *saved_contact_phone.build_tool_spec(owner_display_name, slugs),
        ),
        _fn_tool(
            "phone_call",
            *phone_call.build_tool_spec(owner_display_name, slugs),
        ),
        _fn_tool("reminders", reminders.DESCRIPTION, reminders.SCHEMA),
        _fn_tool("delay_timer", delay_timer.DESCRIPTION, delay_timer.SCHEMA),
        _fn_tool("desktop_notify", desktop_notify.DESCRIPTION, desktop_notify.SCHEMA),
        _fn_tool("volume_control", volume_control.DESCRIPTION, volume_control.SCHEMA),
        _fn_tool("screenshot_desktop", screenshot_desktop.DESCRIPTION, screenshot_desktop.SCHEMA),
        _fn_tool("clipboard_write", clipboard_write.DESCRIPTION, clipboard_write.SCHEMA),
        _fn_tool(
            "xbox_console",
            xbox_console.description_for(owner_display_name),
            xbox_console.SCHEMA,
        ),
        _fn_tool("memory_card", memory_card.DESCRIPTION, memory_card.SCHEMA),
        _fn_tool("run_routine", run_routine.DESCRIPTION, run_routine.SCHEMA),
        _fn_tool("clipboard_ai", clipboard_ai.DESCRIPTION, clipboard_ai.SCHEMA),
        _fn_tool("daily_brief", daily_brief.DESCRIPTION, daily_brief.SCHEMA),
        _fn_tool("badge_status", badge_status.DESCRIPTION, badge_status.SCHEMA),
    ]
    if not disabled:
        return defs
    return [d for d in defs if _tool_name(d) not in disabled]

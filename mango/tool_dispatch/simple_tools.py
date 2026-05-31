"""Simple tool dispatch (no host gates or service wrappers)."""

from __future__ import annotations

from typing import Any, Callable

from mango.config import Config
from mango.tools import (
    badge_status,
    clipboard_ai,
    clipboard_write,
    close_app,
    daily_brief,
    delay_timer,
    desktop_notify,
    globe_state,
    globe_view,
    memory_card,
    open_app,
    product_research,
    reminders,
    screenshot_desktop,
    spotify_play,
    spotify_session,
    spotify_transport,
    system_info,
    therapy_support,
    volume_control,
)

ToolRunner = Callable[[dict[str, Any], Config], str]


def _run_open_app(args: dict[str, Any], _cfg: Config) -> str:
    return open_app.run(**args)


def _run_close_app(args: dict[str, Any], _cfg: Config) -> str:
    return close_app.run(**args)


def _run_spotify_play(args: dict[str, Any], _cfg: Config) -> str:
    return spotify_play.run(**args)


def _run_spotify_transport(args: dict[str, Any], _cfg: Config) -> str:
    return spotify_transport.run(**args)


def _run_spotify_session(args: dict[str, Any], _cfg: Config) -> str:
    return spotify_session.run(**args)


def _run_globe_state(args: dict[str, Any], _cfg: Config) -> str:
    return globe_state.run(**args)


def _run_globe_view(args: dict[str, Any], _cfg: Config) -> str:
    return globe_view.run(**args)


def _run_therapy_support(args: dict[str, Any], _cfg: Config) -> str:
    return therapy_support.run(
        str(args.get("situation") or ""),
        args.get("focus"),
    )


def _run_product_research(args: dict[str, Any], _cfg: Config) -> str:
    return product_research.run(
        str(args.get("product") or ""),
        args.get("angle"),
    )


def _run_system_info(args: dict[str, Any], _cfg: Config) -> str:
    return system_info.run(**args)


def _run_reminders(args: dict[str, Any], _cfg: Config) -> str:
    return reminders.run(**args)


def _run_delay_timer(args: dict[str, Any], _cfg: Config) -> str:
    return delay_timer.run(**args)


def _run_desktop_notify(args: dict[str, Any], _cfg: Config) -> str:
    return desktop_notify.run(**args)


def _run_volume_control(args: dict[str, Any], _cfg: Config) -> str:
    return volume_control.run(**args)


def _run_screenshot_desktop(args: dict[str, Any], _cfg: Config) -> str:
    return screenshot_desktop.run(**args)


def _run_clipboard_write(args: dict[str, Any], _cfg: Config) -> str:
    return clipboard_write.run(**args)


def _run_memory_card(args: dict[str, Any], _cfg: Config) -> str:
    return memory_card.run(**args)


def _run_clipboard_ai(args: dict[str, Any], _cfg: Config) -> str:
    return clipboard_ai.run(**args)


def _run_daily_brief(args: dict[str, Any], _cfg: Config) -> str:
    return daily_brief.run(**args)


def _run_badge_status(args: dict[str, Any], _cfg: Config) -> str:
    return badge_status.run(**args)


SIMPLE_TOOL_DISPATCH: dict[str, ToolRunner] = {
    "open_app": _run_open_app,
    "close_app": _run_close_app,
    "spotify_play": _run_spotify_play,
    "spotify_transport": _run_spotify_transport,
    "spotify_session": _run_spotify_session,
    "globe_state": _run_globe_state,
    "globe_view": _run_globe_view,
    "therapy_support": _run_therapy_support,
    "product_research": _run_product_research,
    "system_info": _run_system_info,
    "reminders": _run_reminders,
    "delay_timer": _run_delay_timer,
    "desktop_notify": _run_desktop_notify,
    "volume_control": _run_volume_control,
    "screenshot_desktop": _run_screenshot_desktop,
    "clipboard_write": _run_clipboard_write,
    "memory_card": _run_memory_card,
    "clipboard_ai": _run_clipboard_ai,
    "daily_brief": _run_daily_brief,
    "badge_status": _run_badge_status,
}


def dispatch_simple_tool(name: str, arguments: dict[str, Any], cfg: Config) -> str | None:
    """Run a simple tool when registered; return None to fall back to registry logic."""
    runner = SIMPLE_TOOL_DISPATCH.get(name)
    if runner is None:
        return None
    return runner(arguments, cfg)

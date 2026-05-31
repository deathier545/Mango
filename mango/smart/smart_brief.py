"""Assemble a daily-style briefing from memory, reminders, and system state."""

from __future__ import annotations

from datetime import UTC, datetime

from mango.smart.smart_store import load_cards, load_inbox


def build_daily_brief() -> str:
    now = datetime.now(UTC).astimezone()
    lines = [f"Daily briefing ({now.strftime('%A %Y-%m-%d %H:%M %Z')})", ""]

    cards = load_cards()
    if cards:
        lines.append("Memory highlights:")
        for c in cards[-8:]:
            lines.append(f"  • [{c.get('category', 'fact')}] {c.get('title')}: {c.get('content', '')}")
        lines.append("")

    inbox = load_inbox()[-5:]
    if inbox:
        lines.append("Recent captures:")
        for item in inbox:
            lines.append(f"  • {item.get('text', '')}")
        lines.append("")

    try:
        from mango.tools import reminders

        rem = reminders.run(action="list")
        if rem and "no pending" not in rem.casefold():
            lines.append("Reminders:")
            lines.append(rem)
            lines.append("")
    except Exception:
        pass

    try:
        from mango.tools import system_info

        lines.append("System:")
        lines.append(system_info.run())
    except Exception:
        lines.append("System: unavailable.")

    try:
        import httpx

        from mango.integrations.discord.discord_voice_client import (
            CONTROL_HEADER,
            control_port,
            control_secret,
        )

        port = control_port()
        headers = {}
        secret = control_secret()
        if secret:
            headers[CONTROL_HEADER] = secret
        r = httpx.get(f"http://127.0.0.1:{port}/v1/voice/status", headers=headers, timeout=2.0)
        if r.status_code == 200:
            lines.append("")
            lines.append("Discord bridge: reachable")
    except Exception:
        lines.append("")
        lines.append("Discord bridge: offline")

    try:
        from mango.badges import compute_badge_snapshot

        snap = compute_badge_snapshot()
        summary = snap.get("summary") or {}
        badge_rows = snap.get("badges") or []
        locked = [b for b in badge_rows if not b.get("unlocked")]
        lines.append("")
        lines.append(
            f"Mango badges: {summary.get('unlocked', 0)}/{summary.get('total', 0)} unlocked "
            f"({summary.get('percent', 0)}% of his progress)."
        )
        if locked:
            lines.append("His next goals:")
            for b in locked[:6]:
                hint = b.get("hint") or b.get("description") or ""
                lines.append(f"  • {b.get('title')}: {hint}")
    except Exception:
        pass

    return "\n".join(lines).strip()

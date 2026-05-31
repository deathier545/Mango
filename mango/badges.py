"""Derive progress badges from Mango's on-disk state and tool timeline."""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path
from typing import Any

from mango.personal_skills import default_skills_dir
from mango.smart.smart_store import (
    load_cards,
    load_inbox,
    load_timeline_entries,
    smart_dir,
)

_MEMORY_CATEGORIES = ("person", "preference", "device", "fact", "task")
_ROUTINE_IDS = (
    "join_discord_play",
    "discord_hi_and_play",
    "night_mode",
    "focus_mode",
)


def _mango_home() -> Path:
    raw = os.getenv("MANGO_SMART_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().parent
    return Path.home() / ".mango"


def _timeline_stats() -> dict[str, Any]:
    """Aggregate tool timeline for badge checks."""
    tools: set[str] = set()
    tool_ok_counts: Counter[str] = Counter()
    ok_count = 0
    routines: set[str] = set()
    discord_hints: set[str] = set()

    for row in load_timeline_entries(5000):
        if not isinstance(row, dict):
            continue
        tool = str(row.get("tool") or "").strip()
        preview = str(row.get("result_preview") or "")
        preview_cf = preview.casefold()
        if row.get("ok") is True and tool:
            tools.add(tool)
            tool_ok_counts[tool] += 1
            ok_count += 1
        if tool == "run_routine":
            for rid in _ROUTINE_IDS:
                if rid in preview_cf:
                    routines.add(rid)
        if tool == "discord_voice" and row.get("ok") is True:
            if any(k in preview_cf for k in ("bridge", "ensure_bridge", "bridge started")):
                discord_hints.add("bridge")
            if any(k in preview_cf for k in ("who", "in call", "participants", "people in")):
                discord_hints.add("rollcall")
            if any(k in preview_cf for k in ("said to", "say_to", "told ", "speaking to")):
                discord_hints.add("direct")
            if any(k in preview_cf for k in ("music", "stream", "playing on discord")):
                discord_hints.add("stream")
            if "greet" in preview_cf:
                discord_hints.add("greet")

    return {
        "tools": tools,
        "tool_ok_counts": tool_ok_counts,
        "ok_count": ok_count,
        "routines": routines,
        "discord_hints": discord_hints,
    }


def _skill_count() -> int:
    skills_dir = os.getenv("MANGO_SKILLS_DIR", "").strip()
    root = Path(skills_dir).expanduser() if skills_dir else default_skills_dir()
    if not root.is_dir():
        return 0
    return sum(1 for p in root.glob("*.md") if p.is_file())


def _persistent_memory_enabled() -> bool:
    raw = os.getenv("MANGO_PERSISTENT_MEMORY", "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _wake_enabled() -> bool:
    raw = os.getenv("MANGO_WAKEWORD", "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _session_log_enabled() -> bool:
    raw = os.getenv("MANGO_SESSION_LOG", "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _memory_days_count(home: Path) -> int:
    days_dir = home / "memory" / "days"
    if not days_dir.is_dir():
        return 0
    return sum(1 for p in days_dir.glob("*.json") if p.is_file())


def _badge(
    *,
    badge_id: str,
    title: str,
    description: str,
    category: str,
    icon: str,
    unlocked: bool,
    hint: str = "",
    current: int = 0,
    target: int = 1,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": badge_id,
        "title": title,
        "description": description,
        "category": category,
        "icon": icon,
        "unlocked": unlocked,
    }
    if hint:
        row["hint"] = hint
    if target > 1 or (not unlocked and current > 0):
        row["progress"] = {"current": min(current, target), "target": target}
    return row


def _build_badges(
    *,
    cards: list[dict[str, Any]],
    inbox: list[dict[str, Any]],
    stats: dict[str, Any],
    skill_count: int,
    home: Path,
) -> list[dict[str, Any]]:
    tools: set[str] = stats["tools"]
    ok_count: int = stats["ok_count"]
    routines: set[str] = stats["routines"]
    discord_hints: set[str] = stats["discord_hints"]

    categories = {str(c.get("category") or "fact") for c in cards}
    category_hits = {cat: sum(1 for c in cards if str(c.get("category") or "fact") == cat) for cat in _MEMORY_CATEGORIES}

    spotify_linked = (home / "spotify_user_token.json").is_file()
    xbox_linked = (home / "xbox_tokens.json").is_file()
    memory_days = _memory_days_count(home)

    def used(tool: str) -> bool:
        return tool in tools

    return [
        _badge(
            badge_id="memory_first",
            title="First Memory",
            description="Saved one memory card about you or your setup.",
            category="memory",
            icon="🧠",
            unlocked=len(cards) >= 1,
            hint="Tell Mango one thing to remember — a preference, person, or device detail.",
            current=len(cards),
            target=1,
        ),
        _badge(
            badge_id="memory_collector",
            title="Five Facts",
            description="Built a small library of five memory cards.",
            category="memory",
            icon="📚",
            unlocked=len(cards) >= 5,
            hint="Save five separate memories across different topics.",
            current=len(cards),
            target=5,
        ),
        _badge(
            badge_id="memory_archivist",
            title="Ten Facts",
            description="Reached ten saved memory cards.",
            category="memory",
            icon="🗄️",
            unlocked=len(cards) >= 10,
            hint="Keep teaching Mango — ten cards makes recall much richer.",
            current=len(cards),
            target=10,
        ),
        _badge(
            badge_id="memory_categories",
            title="Three Categories",
            description="Used at least three different memory card types.",
            category="memory",
            icon="🗂️",
            unlocked=len(categories) >= 3,
            hint="Mix person, preference, device, fact, and task cards — not just one type.",
            current=len(categories),
            target=3,
        ),
        _badge(
            badge_id="memory_complete",
            title="All Categories",
            description="Saved at least one card in every memory type.",
            category="memory",
            icon="🌈",
            unlocked=all(category_hits.get(cat, 0) >= 1 for cat in _MEMORY_CATEGORIES),
            hint="Cover all five types: person, preference, device, fact, and task.",
            current=sum(1 for cat in _MEMORY_CATEGORIES if category_hits.get(cat, 0) >= 1),
            target=len(_MEMORY_CATEGORIES),
        ),
        _badge(
            badge_id="skill_author",
            title="First Skill File",
            description="Created one personal skill markdown file.",
            category="skills",
            icon="✍️",
            unlocked=skill_count >= 1,
            hint="Add one .md guide under ~/.mango/skills/ for something Mango should know.",
            current=skill_count,
            target=1,
        ),
        _badge(
            badge_id="skill_library",
            title="Three Skill Files",
            description="Maintained three personal skill files.",
            category="skills",
            icon="📖",
            unlocked=skill_count >= 3,
            hint="Write separate skill files for different workflows or topics.",
            current=skill_count,
            target=3,
        ),
        _badge(
            badge_id="skill_master",
            title="Five Skill Files",
            description="Maintained five personal skill files.",
            category="skills",
            icon="🎓",
            unlocked=skill_count >= 5,
            hint="A deep skill library lets Mango follow your custom playbooks.",
            current=skill_count,
            target=5,
        ),
        _badge(
            badge_id="routine_join_discord",
            title="Join & Play Flow",
            description="Completed the join Discord and play music routine end-to-end.",
            category="routines",
            icon="🎬",
            unlocked="join_discord_play" in routines,
            hint='Run routine join_discord_play — bridge, join, Spotify, stream in one flow.',
        ),
        _badge(
            badge_id="routine_discord_hi",
            title="Social Hour Flow",
            description="Completed the greet-everyone Discord routine end-to-end.",
            category="routines",
            icon="🎭",
            unlocked="discord_hi_and_play" in routines,
            hint='Run routine discord_hi_and_play — volume, join, greet all, then play.',
        ),
        _badge(
            badge_id="routine_night",
            title="Night Mode Flow",
            description="Ran the night mode wind-down routine.",
            category="routines",
            icon="🌙",
            unlocked="night_mode" in routines,
            hint='Say "night mode" — lowers volume and stops Discord music.',
        ),
        _badge(
            badge_id="routine_focus",
            title="Focus Mode Flow",
            description="Ran the focus mode routine.",
            category="routines",
            icon="🎯",
            unlocked="focus_mode" in routines,
            hint='Say "focus mode" for a quieter desk setup.',
        ),
        _badge(
            badge_id="routine_complete",
            title="All Four Flows",
            description="Ran every built-in routine at least once.",
            category="routines",
            icon="🏁",
            unlocked=len(routines) >= 4,
            hint="Try all four: join & play, social hour, night mode, and focus mode.",
            current=len(routines),
            target=4,
        ),
        _badge(
            badge_id="inbox_capture",
            title="Inbox Starter",
            description="Saved one quick-capture inbox note.",
            category="smart",
            icon="📥",
            unlocked=len(inbox) >= 1,
            hint="Stash a quick thought in Smart → Memory → Quick capture.",
            current=len(inbox),
            target=1,
        ),
        _badge(
            badge_id="inbox_builder",
            title="Five Inbox Notes",
            description="Saved five quick-capture inbox notes.",
            category="smart",
            icon="📝",
            unlocked=len(inbox) >= 5,
            hint="Use the inbox as a scratch pad before promoting notes to memory cards.",
            current=len(inbox),
            target=5,
        ),
        _badge(
            badge_id="smart_brief",
            title="Daily Briefing",
            description="Generated Mango's daily briefing.",
            category="smart",
            icon="☀️",
            unlocked=used("daily_brief"),
            hint='Ask for your daily briefing in chat or Smart → Quick actions.',
        ),
        _badge(
            badge_id="tool_first",
            title="Boot Up",
            description="Completed Mango's first successful tool action on this PC.",
            category="tools",
            icon="⚡",
            unlocked=ok_count >= 1,
            hint="Try any action — open an app, play music, or search the web.",
            current=ok_count,
            target=1,
        ),
        _badge(
            badge_id="tool_spotify",
            title="First Track",
            description="Played a song through Spotify via Mango.",
            category="tools",
            icon="▶️",
            unlocked=used("spotify_play"),
            hint='Say "play [artist or song] on Spotify" — separate from linking your account.',
        ),
        _badge(
            badge_id="tool_web",
            title="Web Lookup",
            description="Used web search for live information.",
            category="tools",
            icon="🔍",
            unlocked=used("web_search"),
            hint='Ask Mango to search the web when you need current facts or news.',
        ),
        _badge(
            badge_id="tool_globe",
            title="Globe View",
            description="Opened the 3D globe for a location.",
            category="tools",
            icon="🌍",
            unlocked=used("globe_view"),
            hint='Ask "show me Tokyo on the globe" or "where is … on the map".',
        ),
        _badge(
            badge_id="tool_screenshot",
            title="Screen Grab",
            description="Captured a desktop screenshot.",
            category="tools",
            icon="📸",
            unlocked=used("screenshot_desktop"),
            hint='Say "take a screenshot" when you need a quick capture.',
        ),
        _badge(
            badge_id="tool_clipboard",
            title="Clipboard Pass",
            description="Read or wrote the clipboard through Mango.",
            category="tools",
            icon="📋",
            unlocked=used("read_clipboard") or used("clipboard_write") or used("clipboard_ai"),
            hint="Ask Mango to read what's copied or paste text for you.",
        ),
        _badge(
            badge_id="tool_files",
            title="File Search",
            description="Searched for files on this PC.",
            category="tools",
            icon="📁",
            unlocked=used("search_files"),
            hint='Ask "find files named …" in your documents or project folders.',
        ),
        _badge(
            badge_id="tool_open_app",
            title="App Open",
            description="Launched an app or website by voice.",
            category="tools",
            icon="🚀",
            unlocked=used("open_app"),
            hint='Try "open Chrome", "open YouTube", or any installed program.',
        ),
        _badge(
            badge_id="tool_powershell",
            title="Shell Command",
            description="Ran an approved PowerShell command.",
            category="tools",
            icon="⌨️",
            unlocked=used("run_powershell"),
            hint="Ask for a whitelisted system check — Mango will request approval if needed.",
        ),
        _badge(
            badge_id="tool_phone",
            title="Phone Dial",
            description="Placed an outbound phone call through Mango.",
            category="tools",
            icon="📞",
            unlocked=used("phone_call"),
            hint="Ask Mango to call someone from your saved contacts.",
        ),
        _badge(
            badge_id="tool_xbox",
            title="Game Remote",
            description="Turned on Xbox or launched a game by voice.",
            category="tools",
            icon="🕹️",
            unlocked=used("xbox_console"),
            hint='After pairing Xbox, say "turn on Xbox" or "launch [game]".',
        ),
        _badge(
            badge_id="tool_therapy",
            title="Check-In",
            description="Used therapy support for emotional grounding.",
            category="tools",
            icon="💚",
            unlocked=used("therapy_support"),
            hint="Share how you're feeling — Mango offers practical coping ideas, not clinical care.",
        ),
        _badge(
            badge_id="tool_product",
            title="Buyer's Eye",
            description="Researched a product before buying.",
            category="tools",
            icon="🛒",
            unlocked=used("product_research"),
            hint="Ask about reviews, safety, or whether a specific product is worth it.",
        ),
        _badge(
            badge_id="tool_reminder",
            title="Timed Reminder",
            description="Set a reminder or delay timer.",
            category="tools",
            icon="⏰",
            unlocked=used("reminders") or used("delay_timer"),
            hint='Say "remind me in 20 minutes to …" or set a countdown timer.',
        ),
        _badge(
            badge_id="tool_notify",
            title="Desktop Alert",
            description="Sent a Windows desktop notification via Mango.",
            category="tools",
            icon="🔔",
            unlocked=used("desktop_notify"),
            hint="Ask Mango to ping your desktop when something finishes.",
        ),
        _badge(
            badge_id="tool_explorer",
            title="Five Tools",
            description="Successfully used five different Mango tools.",
            category="tools",
            icon="🛠️",
            unlocked=len(tools) >= 5,
            hint="Variety counts — try music, files, apps, web, and one routine.",
            current=len(tools),
            target=5,
        ),
        _badge(
            badge_id="tool_master",
            title="Twelve Tools",
            description="Successfully used twelve different Mango tools.",
            category="tools",
            icon="⚙️",
            unlocked=len(tools) >= 12,
            hint="Branch out: globe, screenshot, clipboard, Xbox, phone, and more.",
            current=len(tools),
            target=12,
        ),
        _badge(
            badge_id="tool_veteran",
            title="Fifty Actions",
            description="Completed fifty successful tool actions total.",
            category="tools",
            icon="🏆",
            unlocked=ok_count >= 50,
            hint="Every task Mango completes adds up — keep using him for daily chores.",
            current=ok_count,
            target=50,
        ),
        _badge(
            badge_id="tool_legend",
            title="Two Hundred Actions",
            description="Completed two hundred successful tool actions total.",
            category="tools",
            icon="👑",
            unlocked=ok_count >= 200,
            hint="Make Mango your go-to PC assistant over time.",
            current=ok_count,
            target=200,
        ),
        _badge(
            badge_id="discord_bridge",
            title="Bridge Builder",
            description="Started or verified the Discord voice bridge.",
            category="discord",
            icon="🌉",
            unlocked="bridge" in discord_hints,
            hint='Ask Mango to start the Discord bridge before joining voice.',
        ),
        _badge(
            badge_id="discord_rollcall",
            title="Who's There?",
            description="Asked who is in the Discord call.",
            category="discord",
            icon="👥",
            unlocked="rollcall" in discord_hints,
            hint='Say "who is in the Discord call?" while the bridge is running.',
        ),
        _badge(
            badge_id="discord_direct",
            title="Direct Line",
            description="Spoke to a specific person in Discord voice.",
            category="discord",
            icon="📢",
            unlocked="direct" in discord_hints,
            hint='Try "tell [name] …" or "say hi to [name] in Discord".',
        ),
        _badge(
            badge_id="discord_stream",
            title="Discord Stream",
            description="Streamed Spotify audio into a Discord voice channel.",
            category="discord",
            icon="📡",
            unlocked="stream" in discord_hints,
            hint="Play on Spotify, then start Discord music streaming — not the same as a routine badge.",
        ),
        _badge(
            badge_id="discord_greet_all",
            title="Crowd Hello",
            description="Greeted everyone in the Discord call at once.",
            category="discord",
            icon="🙋",
            unlocked="greet" in discord_hints,
            hint='Ask to "say hello to everyone in call" — distinct from the Social Hour routine badge.',
        ),
        _badge(
            badge_id="integration_spotify",
            title="Spotify Auth",
            description="Authorized Spotify on this PC (account linked).",
            category="integrations",
            icon="🔐",
            unlocked=spotify_linked,
            hint="Complete Spotify sign-in so Mango can access your library — separate from playing a track.",
        ),
        _badge(
            badge_id="integration_xbox",
            title="Xbox Pairing",
            description="Linked your Xbox account on this PC.",
            category="integrations",
            icon="🔗",
            unlocked=xbox_linked,
            hint="Sign in to Xbox in settings — pairing is separate from launching games by voice.",
        ),
        _badge(
            badge_id="continuity_memory",
            title="Persistent Mode",
            description="Turned on cross-restart conversation memory.",
            category="continuity",
            icon="💬",
            unlocked=_persistent_memory_enabled(),
            hint="Enable MANGO_PERSISTENT_MEMORY in your environment.",
        ),
        _badge(
            badge_id="continuity_days",
            title="One Week Saved",
            description="Accumulated seven daily memory snapshots.",
            category="continuity",
            icon="📅",
            unlocked=memory_days >= 7,
            hint="Use Mango across a week with persistent memory enabled.",
            current=memory_days,
            target=7,
        ),
        _badge(
            badge_id="continuity_month",
            title="One Month Saved",
            description="Accumulated thirty daily memory snapshots.",
            category="continuity",
            icon="🗓️",
            unlocked=memory_days >= 30,
            hint="Keep coming back — daily snapshots build automatically.",
            current=memory_days,
            target=30,
        ),
        _badge(
            badge_id="voice_wake",
            title="Wake Word On",
            description="Enabled hands-free wake-word listening.",
            category="voice",
            icon="🎙️",
            unlocked=_wake_enabled(),
            hint="Set MANGO_WAKEWORD=1 so you can say Mango without push-to-talk.",
        ),
        _badge(
            badge_id="setup_session_log",
            title="Session Logs On",
            description="Enabled session transcript logging to disk.",
            category="voice",
            icon="📜",
            unlocked=_session_log_enabled(),
            hint="Set MANGO_SESSION_LOG=1 to keep logs under ~/.mango/logs.",
        ),
    ]


def compute_badge_snapshot() -> dict[str, Any]:
    cards = load_cards()
    inbox = load_inbox()
    stats = _timeline_stats()
    skill_count = _skill_count()
    home = _mango_home()

    badges = _build_badges(
        cards=cards,
        inbox=inbox,
        stats=stats,
        skill_count=skill_count,
        home=home,
    )

    unlocked = sum(1 for b in badges if b.get("unlocked"))
    total = len(badges)
    return {
        "badges": badges,
        "summary": {
            "unlocked": unlocked,
            "total": total,
            "percent": round((unlocked / total) * 100) if total else 0,
        },
        "smart_dir": str(smart_dir()),
    }


def _badge_progress_ratio(badge: dict[str, Any]) -> float:
    prog = badge.get("progress")
    if not isinstance(prog, dict):
        return 0.0
    target = int(prog.get("target") or 0)
    if target <= 0:
        return 0.0
    return min(1.0, int(prog.get("current") or 0) / target)


def badges_for_prompt(*, max_locked: int = 6, max_unlocked: int = 4) -> str:
    """Compact badge block for the system prompt — goals Mango should help complete."""
    snap = compute_badge_snapshot()
    badges: list[dict[str, Any]] = snap["badges"]
    summary = snap["summary"]

    unlocked = [b for b in badges if b.get("unlocked")]
    locked = [b for b in badges if not b.get("unlocked")]
    locked.sort(key=_badge_progress_ratio, reverse=True)

    lines = [
        (
            f"My progress badges ({summary['unlocked']}/{summary['total']} unlocked — "
            "Smart tab → Badges). Details also via badge_status tool."
        ),
    ]

    if unlocked:
        lines.append("")
        lines.append("I've unlocked:")
        for badge in unlocked[-max_unlocked:]:
            lines.append(f"- {badge['title']}: {badge['description']}")

    if locked:
        lines.append("")
        lines.append("Still locked for me:")
        for badge in locked[:max_locked]:
            hint = str(badge.get("hint") or badge.get("description") or "").strip()
            prog = badge.get("progress")
            prog_s = ""
            if isinstance(prog, dict) and int(prog.get("target") or 0) > 1:
                prog_s = f" [{prog.get('current')}/{prog.get('target')}]"
            lines.append(f"- {badge['title']}{prog_s}: {hint}")

    return "\n".join(lines)


def _badge_question_kind(user_text: str) -> str:
    """Classify badge-related user message: motivation, suggest, or status."""
    low = (user_text or "").strip().casefold()
    if not low:
        return "status"
    motivation_markers = (
        "want to unlock",
        "want more badge",
        "like to earn",
        "like to unlock",
        "should we unlock",
        "should you unlock",
        "help you unlock",
        "help you earn",
        "try to unlock",
        "keep unlocking",
        "get more badge",
    )
    if any(m in low for m in motivation_markers):
        return "motivation"
    if "do you want" in low and re.search(r"\bbadge", low):
        return "motivation"
    if any(
        p in low
        for p in (
            "which badge",
            "what badge",
            "what should we work on",
            "suggest a badge",
            "pick a badge",
        )
    ):
        return "suggest"
    return "status"


def _pick_badge_line(seed: str, *lines: str) -> str:
    if not lines:
        return ""
    return lines[sum(ord(c) for c in seed) % len(lines)]


def format_badge_reply(user_text: str = "", *, next_locked: int = 3) -> str:
    """Spoken/chat reply about Mango's badge progress — status, motivation, or suggestions."""
    snap = compute_badge_snapshot()
    summary = snap["summary"]
    badge_rows: list[dict[str, Any]] = snap["badges"]
    locked = [b for b in badge_rows if not b.get("unlocked")]
    locked.sort(key=_badge_progress_ratio, reverse=True)

    unlocked_n = int(summary.get("unlocked") or 0)
    total_n = int(summary.get("total") or 0)
    percent = int(summary.get("percent") or 0)
    remaining = max(0, total_n - unlocked_n)
    kind = _badge_question_kind(user_text)
    seed = (user_text or "badge").casefold()

    if not locked:
        return _pick_badge_line(
            seed,
            "I've unlocked every badge on my list so far — I'm in good shape, but I'm always up for new challenges with you.",
            "I'm at one hundred percent on my badges right now. Still happy to push into new stuff whenever you are.",
        )

    top = locked[0]
    top_title = str(top.get("title") or "my next goal")
    top_hint = str(top.get("hint") or top.get("description") or "").strip()
    names = ", ".join(str(b.get("title") or "goal") for b in locked[:next_locked])

    if kind == "motivation":
        hint_bit = f" {top_hint}" if top_hint else ""
        return _pick_badge_line(
            seed,
            (
                f"Yeah — I want to keep going. I'm at {unlocked_n} of {total_n} badges, "
                f"and {top_title} is next on my list.{hint_bit} Want to help me knock that out?"
            ),
            (
                f"Definitely. I've still got {remaining} badges to earn, and {top_title} "
                f"is the closest win.{hint_bit} Should we go for it?"
            ),
            (
                f"I do — each badge means I'm getting more useful on this PC. "
                f"Next up is {top_title}.{hint_bit} Want to tackle that together?"
            ),
        )

    if kind == "suggest":
        hint_bit = f" {top_hint}" if top_hint else ""
        return _pick_badge_line(
            seed,
            (
                f"I'd start with {top_title} — it's my nearest unlock.{hint_bit} "
                f"After that, {names.split(', ')[1] if ', ' in names else 'the next ones on my list'}."
            ),
            (
                f"Easiest win for me is probably {top_title}.{hint_bit} "
                f"My other targets are {names}."
            ),
        )

    parts = [
        f"I'm at {unlocked_n} of {total_n} badges — {percent} percent through my set.",
        f"I still want {remaining} more; my next targets are {names}.",
    ]
    if top_hint:
        parts.append(f"For {top_title}, {top_hint}")
    parts.append("Full list is under Smart → Badges if you want to browse.")
    return " ".join(parts)


def format_badge_spoken_summary(*, next_locked: int = 3) -> str:
    """Backward-compatible alias — prefer format_badge_reply with user_text when available."""
    return format_badge_reply("", next_locked=next_locked)

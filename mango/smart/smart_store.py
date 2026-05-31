"""Global smart layer: memory cards, routines, capture inbox (JSON on disk)."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_ROUTINES: list[dict[str, Any]] = [
    {
        "id": "join_discord_play",
        "name": "Join Discord + play music",
        "description": "Sync voice bridge, play Spotify query, start Discord music stream.",
        "steps": [
            {"tool": "discord_voice", "arguments": {"action": "ensure_bridge"}},
            {"tool": "discord_voice", "arguments": {"action": "sync"}},
            {"tool": "spotify_play", "arguments": {"query": "{{query}}"}},
            {"tool": "discord_voice", "arguments": {"action": "music_start"}},
        ],
    },
    {
        "id": "discord_hi_and_play",
        "name": "Join Discord, greet everyone, play music",
        "description": "Join call, greet known guests, play Spotify query, stream to Discord, set volume.",
        "steps": [
            {
                "tool": "volume_control",
                "arguments": {"action": "set", "percent": "{{volume}}"},
            },
            {"tool": "discord_voice", "arguments": {"action": "ensure_bridge"}},
            {"tool": "discord_voice", "arguments": {"action": "sync"}},
            {"tool": "discord_voice", "arguments": {"action": "greet_everyone"}},
            {"tool": "spotify_play", "arguments": {"query": "{{query}}"}},
            {"tool": "discord_voice", "arguments": {"action": "music_start"}},
        ],
    },
    {
        "id": "night_mode",
        "name": "Night mode",
        "description": "Lower volume and stop Discord music stream.",
        "steps": [
            {"tool": "volume_control", "arguments": {"action": "set", "percent": 25}},
            {"tool": "discord_voice", "arguments": {"action": "music_stop"}},
            {"tool": "desktop_notify", "arguments": {"title": "Mango", "message": "Night mode on."}},
        ],
    },
    {
        "id": "focus_mode",
        "name": "Focus mode",
        "description": "Mute notifications cue and set moderate volume.",
        "steps": [
            {"tool": "volume_control", "arguments": {"action": "set", "percent": 40}},
            {"tool": "desktop_notify", "arguments": {"title": "Mango", "message": "Focus mode — say mango when ready."}},
        ],
    },
]


def smart_dir() -> Path:
    raw = os.getenv("MANGO_SMART_DIR", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".mango" / "smart"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return default


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _legacy_discord_hi_volume_last(steps: Any) -> bool:
    if not isinstance(steps, list) or not steps:
        return False
    last = steps[-1]
    return isinstance(last, dict) and last.get("tool") == "volume_control"


def _upgrade_legacy_discord_routines(
    routines: list[dict[str, Any]],
) -> list[dict[str, Any]] | None:
    """Replace old discord_hi_and_play step order (volume last) with current defaults."""
    defaults = {str(r.get("id")): r for r in _DEFAULT_ROUTINES if r.get("id")}
    out: list[dict[str, Any]] = []
    changed = False
    for r in routines:
        if not isinstance(r, dict):
            out.append(r)
            continue
        rid = str(r.get("id") or "")
        if rid == "discord_hi_and_play" and _legacy_discord_hi_volume_last(r.get("steps")):
            repl = defaults.get(rid)
            if repl:
                out.append(dict(repl))
                changed = True
                continue
        out.append(r)
    return out if changed else None


def ensure_defaults() -> None:
    root = smart_dir()
    root.mkdir(parents=True, exist_ok=True)
    cards = root / "cards.json"
    if not cards.is_file():
        save_cards([])
    routines_path = root / "routines.json"
    if not routines_path.is_file():
        save_routines(list(_DEFAULT_ROUTINES))
    else:
        data = _read_json(routines_path, {"routines": []})
        existing = data.get("routines") if isinstance(data, dict) else []
        if not isinstance(existing, list):
            existing = []
        known_ids = {r.get("id") for r in existing if isinstance(r, dict)}
        merged = [r for r in existing if isinstance(r, dict)]
        changed = False
        for default in _DEFAULT_ROUTINES:
            if default.get("id") not in known_ids:
                merged.append(default)
                changed = True
        if changed:
            save_routines(merged)
        merged = _upgrade_legacy_discord_routines(merged)
        if merged is not None:
            save_routines(merged)
    inbox = root / "inbox.json"
    if not inbox.is_file():
        _atomic_write(inbox, json.dumps({"version": 1, "items": []}, indent=2))


def load_cards() -> list[dict[str, Any]]:
    ensure_defaults()
    data = _read_json(smart_dir() / "cards.json", {"cards": []})
    cards = data.get("cards") if isinstance(data, dict) else []
    return [c for c in cards if isinstance(c, dict)]


def save_cards(cards: list[dict[str, Any]]) -> None:
    payload = {"version": 1, "updated_at": _now_iso(), "cards": cards}
    _atomic_write(smart_dir() / "cards.json", json.dumps(payload, indent=2, ensure_ascii=False))


def upsert_card(
    *,
    title: str,
    content: str,
    category: str = "fact",
    card_id: str | None = None,
) -> dict[str, Any]:
    cards = load_cards()
    now = _now_iso()
    cid = (card_id or "").strip() or uuid.uuid4().hex[:12]
    entry = {
        "id": cid,
        "title": title.strip() or "Untitled",
        "content": content.strip(),
        "category": (category or "fact").strip().lower(),
        "updated_at": now,
    }
    replaced = False
    for i, c in enumerate(cards):
        if c.get("id") == cid:
            entry["created_at"] = c.get("created_at") or now
            cards[i] = entry
            replaced = True
            break
    if not replaced:
        entry["created_at"] = now
        cards.append(entry)
    save_cards(cards)
    return entry


def delete_card(card_id: str) -> bool:
    cards = load_cards()
    n0 = len(cards)
    cards = [c for c in cards if c.get("id") != card_id]
    if len(cards) == n0:
        return False
    save_cards(cards)
    return True


def cards_for_prompt(max_cards: int = 24) -> str:
    cards = load_cards()[-max_cards:]
    if not cards:
        return ""
    lines = ["User facts (for context — do not read labels or IDs aloud):"]
    for c in cards:
        lines.append(f"- [{c.get('category', 'fact')}] {c.get('title', '')}: {c.get('content', '')}")
    return "\n".join(lines)


def load_routines() -> list[dict[str, Any]]:
    ensure_defaults()
    data = _read_json(smart_dir() / "routines.json", {"routines": []})
    routines = data.get("routines") if isinstance(data, dict) else []
    return [r for r in routines if isinstance(r, dict)]


def save_routines(routines: list[dict[str, Any]]) -> None:
    payload = {"version": 1, "updated_at": _now_iso(), "routines": routines}
    _atomic_write(smart_dir() / "routines.json", json.dumps(payload, indent=2, ensure_ascii=False))


def load_inbox() -> list[dict[str, Any]]:
    ensure_defaults()
    data = _read_json(smart_dir() / "inbox.json", {"items": []})
    items = data.get("items") if isinstance(data, dict) else []
    return [i for i in items if isinstance(i, dict)]


def add_inbox_item(text: str, *, tags: list[str] | None = None) -> dict[str, Any]:
    items = load_inbox()
    item = {
        "id": uuid.uuid4().hex[:12],
        "text": text.strip(),
        "tags": list(tags or []),
        "created_at": _now_iso(),
    }
    items.append(item)
    payload = {"version": 1, "updated_at": _now_iso(), "items": items[-200:]}
    _atomic_write(smart_dir() / "inbox.json", json.dumps(payload, indent=2, ensure_ascii=False))
    return item


def smart_snapshot() -> dict[str, Any]:
    ensure_defaults()
    from mango.badges import compute_badge_snapshot

    return {
        "cards": load_cards(),
        "routines": load_routines(),
        "inbox": load_inbox(),
        "timeline": load_timeline_entries(80),
        "badges": compute_badge_snapshot(),
    }


def load_timeline_entries(limit: int = 100) -> list[dict[str, Any]]:
    path = smart_dir() / "timeline.jsonl"
    if not path.is_file():
        return []
    lines: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                out.append(row)
        except json.JSONDecodeError:
            continue
    return out

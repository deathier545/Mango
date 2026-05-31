"""Persistent reminders in ~/.mango/reminders.json + background watchdog."""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def reminders_path() -> Path:
    return Path.home() / ".mango" / "reminders.json"


def load_reminders() -> list[dict[str, Any]]:
    p = reminders_path()
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else []
    except Exception:
        logger.warning("Could not parse reminders file", exc_info=True)
        return []


def save_reminders(rows: list[dict[str, Any]]) -> None:
    p = reminders_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def add_reminder_minutes(minutes: float, message: str) -> tuple[str, str]:
    """Schedule a reminder; returns (id, summary line for the model)."""
    msg = (message or "").strip() or "Reminder"
    m = max(0.5, min(float(minutes), 10080.0))  # up to 7 days
    fire = time.time() + m * 60.0
    rid = uuid.uuid4().hex[:12]
    rows = load_reminders()
    rows.append(
        {
            "id": rid,
            "fire_at_unix": fire,
            "message": msg[:2000],
            "created_unix": time.time(),
        }
    )
    save_reminders(rows)
    human_m = int(round(m))
    return rid, f"Reminder set for {human_m} minute(s) from now (id {rid})."


def list_reminders_text() -> str:
    rows = load_reminders()
    now = time.time()
    lines: list[str] = []
    for row in rows[:40]:
        rid = str(row.get("id") or "")
        msg = str(row.get("message") or "").strip()
        try:
            fire = float(row.get("fire_at_unix", 0))
        except (TypeError, ValueError):
            continue
        remain = max(0.0, fire - now)
        lines.append(f"- {rid}: in {remain / 60.0:.1f} min — {msg[:120]}")
    if not lines:
        return "No pending reminders."
    return "Pending reminders:\n" + "\n".join(lines)


def cancel_reminder(reminder_id: str) -> str:
    rid = (reminder_id or "").strip().lower()
    if not rid:
        return "Error: missing reminder id."
    rows = load_reminders()
    kept = [r for r in rows if str(r.get("id") or "").lower() != rid]
    if len(kept) == len(rows):
        return f"No reminder with id {rid!r}."
    save_reminders(kept)
    return f"Cancelled reminder {rid}."


def _notify(title: str, message: str) -> None:
    try:
        from plyer import notification

        notification.notify(
            title=title[:64],
            message=message[:256],
            app_name="Mango",
            timeout=14,
        )
    except Exception:
        logger.warning("Reminder toast failed", exc_info=True)


def process_due_reminders() -> None:
    now = time.time()
    rows = load_reminders()
    kept: list[dict[str, Any]] = []
    for row in rows:
        try:
            fire = float(row.get("fire_at_unix", 0))
        except (TypeError, ValueError):
            kept.append(row)
            continue
        if fire <= now:
            msg = str(row.get("message") or "Reminder").strip() or "Reminder"
            _notify("Mango reminder", msg)
            logger.info("Fired reminder id=%s", row.get("id"))
        else:
            kept.append(row)
    if len(kept) != len(rows):
        save_reminders(kept)


def start_watchdog(stop_event: threading.Event, *, interval_sec: float = 12.0) -> None:
    def loop() -> None:
        while not stop_event.wait(interval_sec):
            try:
                process_due_reminders()
            except Exception:
                logger.exception("Reminder watchdog tick failed")

    threading.Thread(target=loop, daemon=True, name="MangoReminderWatchdog").start()

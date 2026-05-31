from __future__ import annotations

import json
import logging

from mango.desktop_events import emit_desktop_event


def test_emit_desktop_event_logs_json_prefix(caplog) -> None:
    caplog.set_level(logging.INFO)
    emit_desktop_event({"type": "state", "state": "thinking"})
    assert any("MANGO_EVENT:" in rec.message for rec in caplog.records)
    line = next(rec.message for rec in caplog.records if "MANGO_EVENT:" in rec.message)
    payload = json.loads(line.split("MANGO_EVENT:", 1)[1].strip())
    assert payload["type"] == "state"
    assert payload["state"] == "thinking"

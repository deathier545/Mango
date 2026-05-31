from __future__ import annotations

from mango.handoff_contracts import validate_handoff_payload


def test_handoff_contract_music_requires_query():
    ok, reason = validate_handoff_payload("music", {"query": "play daft punk"})
    assert ok is True
    ok2, reason2 = validate_handoff_payload("music", {})
    assert ok2 is False
    assert "Missing required fields" in reason2


def test_handoff_contract_unknown_domain():
    ok, reason = validate_handoff_payload("unknown", {"x": "y"})
    assert ok is False
    assert "Unknown handoff domain" in reason

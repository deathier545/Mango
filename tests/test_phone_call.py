from __future__ import annotations

import pytest

from mango.tools import phone_call


@pytest.fixture
def _signalwire_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Minimal SignalWire config so phone_call reaches host-approval gating in tests."""
    monkeypatch.setenv("MANGO_PHONE_PROVIDER", "signalwire")
    monkeypatch.setenv("SIGNALWIRE_PROJECT_ID", "test-project")
    monkeypatch.setenv("SIGNALWIRE_API_TOKEN", "test-token-not-placeholder")
    monkeypatch.setenv("SIGNALWIRE_SPACE_URL", "example.signalwire.com")
    monkeypatch.setenv("SIGNALWIRE_FROM_NUMBER", "+15551234567")


def test_phone_call_unknown_voicemail_policy(monkeypatch):
    monkeypatch.setenv("MANGO_CONTACT_ARIANA_PHONE", "+17742625151")
    out = phone_call.run(
        "ariana",
        voicemail_policy="weird",
        _host_approved=False,
        _allowed_contacts=("ariana",),
    )
    assert out.startswith("PHONE_CALL_FAILED:")


def test_phone_call_rejects_bad_transfer_number(monkeypatch, _signalwire_env: None):
    monkeypatch.setenv("MANGO_CONTACT_ARIANA_PHONE", "+17742625151")
    out = phone_call.run(
        "ariana",
        transfer_to="555-1234",
        _host_approved=False,
        _allowed_contacts=("ariana",),
    )
    assert "transfer_to must be a valid" in out


def test_phone_call_pending_includes_confirmation_text(monkeypatch, _signalwire_env: None):
    monkeypatch.setenv("MANGO_CONTACT_ARIANA_PHONE", "+17742625151")
    out = phone_call.run(
        "ariana",
        message="hello there",
        voicemail_policy="brief",
        _host_approved=False,
        _allowed_contacts=("ariana",),
    )
    assert out.startswith("HOST_PENDING_PHONE_CALL:")

"""Outbound phone calls through a Twilio-compatible Voice API."""

from __future__ import annotations

import html
import logging
import os
import re
from typing import Any

import httpx

from mango.persona import owner_display_name_from_env
from mango.timeouts import PHONE_CALL_HTTP_S

logger = logging.getLogger(__name__)

_E164 = re.compile(r"^\+[1-9]\d{7,14}$")
_TOKEN_PLACEHOLDERS = {
    "",
    "ROTATE_AND_PASTE_NEW_TOKEN_HERE",
    "PASTE_ROTATED_TOKEN_HERE",
}


def _slug_display(slug: str) -> str:
    key = f"MANGO_CONTACT_{slug.upper()}_DISPLAY"
    raw = os.getenv(key, "").strip()
    if raw:
        return raw
    return slug.replace("_", " ").strip().title() or slug


def _english_join(labels: list[str]) -> str:
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} or {labels[1]}"
    return ", ".join(labels[:-1]) + f", or {labels[-1]}"


def build_tool_spec(owner: str, slugs: tuple[str, ...]) -> tuple[str, dict[str, Any]]:
    """LLM function name ``phone_call``: description + JSON schema for configured contacts."""
    labels = [_slug_display(s) for s in slugs]
    human = _english_join(labels)
    desc = (
        "Place an outbound phone call through SignalWire or Twilio to a saved contact. Use when "
        f"{owner} asks Mango to call or dial {human} by phone. Include a short message for after pickup when relevant. "
        "Do not use this when they only want to hear the saved number from .env — use saved_contact_phone for that. "
        "Depending on host settings, a separate spoken confirmation before dialing may or may not be required."
    )
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "contact": {
                "type": "string",
                "enum": list(slugs),
                "description": "Saved contact to call.",
            },
            "message": {
                "type": "string",
                "description": (
                    "Short message for Mango to say after the call is answered. If omitted, Mango says "
                    "a brief hello and identifies itself."
                ),
            },
            "voicemail_policy": {
                "type": "string",
                "enum": ["leave_message", "brief", "hangup"],
                "description": (
                    "How to behave when call reaches voicemail-like greeting: "
                    "leave_message (default), brief (short line), or hangup."
                ),
            },
            "transfer_to": {
                "type": "string",
                "description": "Optional E.164 number (+1...) to transfer to after greeting (warm transfer style).",
            },
        },
        "required": ["contact"],
        "additionalProperties": False,
    }
    return desc, schema


def _contact_phone(contact: str) -> str:
    key = re.sub(r"[^A-Za-z0-9]+", "_", contact).upper().strip("_")
    return os.getenv(f"MANGO_CONTACT_{key}_PHONE", "").strip()


def _contact_display(contact: str) -> str:
    return _slug_display(contact)


def _twiml(message: str, *, transfer_to: str | None = None, hangup: bool = False) -> str:
    safe = html.escape(message.strip(), quote=False)
    transfer_xml = f"\n  <Dial>{html.escape(transfer_to, quote=False)}</Dial>" if transfer_to else ""
    hangup_xml = "\n  <Hangup/>" if hangup else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice">{safe}</Say>{transfer_xml}{hangup_xml}
</Response>"""


def _default_message(contact: str, owner: str) -> str:
    return f"Hello {_contact_display(contact)}. This is Mango calling for {owner}."


def _provider_settings() -> tuple[str, str, str, str, str] | str:
    provider = (os.getenv("MANGO_PHONE_PROVIDER", "signalwire").strip().casefold() or "signalwire")
    if provider == "signalwire":
        project_id = os.getenv("SIGNALWIRE_PROJECT_ID", "").strip()
        token = os.getenv("SIGNALWIRE_API_TOKEN", "").strip()
        space_url = os.getenv("SIGNALWIRE_SPACE_URL", "").strip().removeprefix("https://").rstrip("/")
        from_number = os.getenv("SIGNALWIRE_FROM_NUMBER", "").strip()
        if not project_id:
            return "SIGNALWIRE_PROJECT_ID is missing in .env."
        if token in _TOKEN_PLACEHOLDERS:
            return "SIGNALWIRE_API_TOKEN is missing in .env."
        if not space_url:
            return "SIGNALWIRE_SPACE_URL is missing in .env."
        if not _E164.match(from_number):
            return "SIGNALWIRE_FROM_NUMBER is missing or not in +1... E.164 format."
        url = f"https://{space_url}/api/laml/2010-04-01/Accounts/{project_id}/Calls.json"
        return provider, url, project_id, token, from_number

    if provider == "twilio":
        sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
        token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
        from_number = os.getenv("TWILIO_FROM_NUMBER", "").strip()
        if not sid.startswith("AC"):
            return "TWILIO_ACCOUNT_SID is missing or invalid in .env."
        if token in _TOKEN_PLACEHOLDERS:
            return "TWILIO_AUTH_TOKEN is not configured in .env."
        if not _E164.match(from_number):
            return "TWILIO_FROM_NUMBER is missing or not in +1... E.164 format."
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json"
        return provider, url, sid, token, from_number

    return f"Unknown MANGO_PHONE_PROVIDER {provider!r}. Use signalwire or twilio."


def run(
    contact: str,
    message: str | None = None,
    voicemail_policy: str | None = None,
    transfer_to: str | None = None,
    *,
    _host_approved: bool = False,
    _allowed_contacts: tuple[str, ...] | None = None,
) -> str:
    """Place an outbound call, but only after host approval when confirmations are on."""
    allowed = _allowed_contacts if _allowed_contacts else ("ariana", "brooke", "dylan")
    owner = owner_display_name_from_env()
    contact_key = (contact or "").strip().casefold()
    if contact_key not in allowed:
        human = _english_join([_slug_display(s) for s in allowed])
        return f"PHONE_CALL_FAILED: Unknown phone contact. Use {human}."

    display = _contact_display(contact_key)
    to_number = _contact_phone(contact_key)
    if not to_number:
        return (
            f"PHONE_CALL_FAILED: No phone number is configured for {display}. Add "
            f"MANGO_CONTACT_{contact_key.upper()}_PHONE=+1... to .env."
        )
    if not _E164.match(to_number):
        return f"PHONE_CALL_FAILED: Configured phone number for {display} is not valid E.164 format: {to_number!r}."

    provider_config = _provider_settings()
    if isinstance(provider_config, str):
        return f"PHONE_CALL_FAILED: {provider_config}"
    provider, url, account_id, token, from_number = provider_config

    spoken = (message or "").strip() or _default_message(contact_key, owner)
    spoken = spoken[:800]
    vm = (voicemail_policy or "leave_message").strip().lower() or "leave_message"
    if vm not in {"leave_message", "brief", "hangup"}:
        return f"PHONE_CALL_FAILED: Unknown voicemail_policy {vm!r}."
    transfer = (transfer_to or "").strip()
    if transfer and not _E164.match(transfer):
        return "PHONE_CALL_FAILED: transfer_to must be a valid +1... E.164 number."
    if vm == "brief":
        spoken = f"Hi {_contact_display(contact_key)}, this is Mango calling for {owner}. Please call back."
    if vm == "hangup":
        spoken = "Hello. This is Mango calling for " + owner + ". Goodbye."

    if not _host_approved:
        return (
            f"HOST_PENDING_PHONE_CALL: NOT_DIALED. Ask {owner} to confirm calling {display} at "
            f"{to_number} and saying: {spoken!r}. If they clearly agree, call phone_call again "
            f"with the same contact and message. Do not tell {owner} the call was placed yet."
        )

    data = {
        "To": to_number,
        "From": from_number,
        "Twiml": _twiml(
            spoken,
            transfer_to=transfer or None,
            hangup=(vm == "hangup" and not transfer),
        ),
    }
    try:
        with httpx.Client(timeout=PHONE_CALL_HTTP_S) as client:
            resp = client.post(url, data=data, auth=(account_id, token))
        if resp.status_code >= 400:
            logger.warning("%s call failed status=%s body=%r", provider, resp.status_code, resp.text[:500])
            return f"PHONE_CALL_FAILED: {provider.title()} call failed: HTTP {resp.status_code}: {resp.text[:300]}"
        payload = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("%s HTTP error: %s", provider, exc)
        return f"PHONE_CALL_FAILED: {provider.title()} HTTP error: {exc}"
    except (ValueError, TypeError) as exc:
        logger.warning("phone_call response parse error: %s", exc, exc_info=True)
        return f"PHONE_CALL_FAILED: {provider.title()} returned invalid JSON payload."

    call_sid = str(payload.get("sid") or "").strip()
    status = str(payload.get("status") or "queued").strip()
    transfer_note = f" Warm transfer target: {transfer}." if transfer else ""
    return (
        f"PHONE_CALL_PLACED: Calling {display} now through {provider.title()}. "
        f"Status: {status}. Voicemail policy: {vm}.{transfer_note} "
        f"Call SID: {call_sid or 'unknown'}."
    )

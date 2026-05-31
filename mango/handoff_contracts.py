"""Specialist handoff contracts between assistant domains."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HandoffContract:
    domain: str
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...] = ()


_CONTRACTS: dict[str, HandoffContract] = {
    "music": HandoffContract(
        domain="music",
        required_fields=("query",),
        optional_fields=("uri", "source", "device"),
    ),
    "phone": HandoffContract(
        domain="phone",
        required_fields=("contact",),
        optional_fields=("message", "provider"),
    ),
    "desktop": HandoffContract(
        domain="desktop",
        required_fields=("action",),
        optional_fields=("target", "app_name"),
    ),
    "research": HandoffContract(
        domain="research",
        required_fields=("query",),
        optional_fields=("angle",),
    ),
}


def contract_for_domain(domain: str) -> HandoffContract | None:
    return _CONTRACTS.get((domain or "").strip().lower())


def validate_handoff_payload(domain: str, payload: dict[str, Any]) -> tuple[bool, str]:
    c = contract_for_domain(domain)
    if c is None:
        return False, f"Unknown handoff domain: {domain!r}"
    missing = [f for f in c.required_fields if not str(payload.get(f, "")).strip()]
    if missing:
        return False, f"Missing required fields for {domain}: {', '.join(missing)}"
    return True, "ok"

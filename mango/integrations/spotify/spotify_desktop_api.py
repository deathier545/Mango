"""Start playback on the Spotify **desktop** app via Web API (Connect).

Opening ``spotify:`` URIs or spawning ``Spotify.exe --uri=…`` often **restores/focuses** the Spotify window.
The Web API can queue playback on an already-running **Computer** device with much less UI churn.
Requires **Premium**, **spotify_session** login (same token as web playback), and scopes in ``spotify_user_auth``.
"""

from __future__ import annotations

import logging
import os
import urllib.parse
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def desktop_connect_api_enabled() -> bool:
    """When true (default), ``spotify_play`` tries Connect API before URI handoff if a user token exists."""
    return os.getenv("MANGO_SPOTIFY_DESKTOP_API", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _device_name_hint() -> str:
    return os.getenv("MANGO_SPOTIFY_DEVICE_NAME", "").strip().lower()


def _clean_track_uri(uri: str) -> str:
    u = uri.strip()
    if u.lower().endswith(":play"):
        return u[: len(u) - 5]
    return u


def fetch_devices(access: str) -> tuple[list[dict[str, Any]], str | None]:
    try:
        r = httpx.get(
            "https://api.spotify.com/v1/me/player/devices",
            headers={"Authorization": f"Bearer {access}"},
            timeout=20.0,
        )
    except httpx.HTTPError as exc:
        return [], str(exc)
    if r.status_code != 200:
        return [], f"devices HTTP {r.status_code}: {r.text[:200]}"
    data = r.json()
    devs = data.get("devices") if isinstance(data, dict) else None
    if not isinstance(devs, list):
        return [], "Unexpected devices response."
    out = [d for d in devs if isinstance(d, dict)]
    return out, None


def pick_device_id(devices: list[dict[str, Any]]) -> str | None:
    """Prefer name hint, then ``Computer`` (desktop), then active device, then any unrestricted device."""
    hint = _device_name_hint()
    usable = [d for d in devices if not d.get("is_restricted")]
    if not usable:
        usable = list(devices)
    if hint:
        for d in usable:
            if hint in str(d.get("name") or "").casefold():
                did = d.get("id")
                if isinstance(did, str) and did.strip():
                    return did.strip()
    for d in usable:
        if str(d.get("type") or "").casefold() == "computer":
            did = d.get("id")
            if isinstance(did, str) and did.strip():
                return did.strip()
    for d in usable:
        if d.get("is_active"):
            did = d.get("id")
            if isinstance(did, str) and did.strip():
                return did.strip()
    for d in usable:
        did = d.get("id")
        if isinstance(did, str) and did.strip():
            return did.strip()
    return None


def play_track_uri(access: str, launch_uri: str) -> tuple[bool, str]:
    """``PUT /me/player/play`` on a Connect device. ``launch_uri`` may include ``:play`` (stripped for JSON)."""
    clean = _clean_track_uri(launch_uri)
    if not clean.lower().startswith("spotify:track:"):
        return False, "Connect API path expects a spotify:track URI."

    devices, err = fetch_devices(access)
    if err:
        return False, err
    if not devices:
        return (
            False,
            "No Spotify Connect devices — open the Spotify desktop app and leave it logged in, then try again.",
        )
    did = pick_device_id(devices)
    if not did:
        return False, "Could not pick a Spotify device id."

    enc = urllib.parse.quote(did, safe="")
    try:
        r = httpx.put(
            f"https://api.spotify.com/v1/me/player/play?device_id={enc}",
            headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"},
            json={"uris": [clean]},
            timeout=25.0,
        )
    except httpx.HTTPError as exc:
        return False, str(exc)
    if r.status_code in (200, 204):
        return True, "Queued via Spotify Connect (Web API)."
    if r.status_code == 404:
        return (
            False,
            "No active Spotify player for this account — open the desktop app once, then retry.",
        )
    if r.status_code == 403:
        return False, "Spotify refused playback (Premium + user-modify-playback-state required)."
    return False, f"Connect play HTTP {r.status_code}: {r.text[:240]}"

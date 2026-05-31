"""Open a browser map view for a place (OpenStreetMap, framed on geocoded bbox)."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

import mango.desktop.desktop_ipc as desktop_ipc
from mango.desktop.globe_server import build_globe_url

logger = logging.getLogger(__name__)

DESCRIPTION = (
    "Show a named place in Mango map mode when the user asks where something is on the map. "
    "Uses geocoded bbox for framing when available."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "place": {
            "type": "string",
            "description": "Place name to find and show (e.g. China, Paris, Lake Michigan).",
        },
    },
    "required": ["place"],
    "additionalProperties": False,
}

_NOMINATIM = "https://nominatim.openstreetmap.org/search"


def _geocode(place: str) -> tuple[float, float, str, dict[str, float] | None] | str:
    q = (place or "").strip()
    if not q:
        return "Error: empty place."
    headers = {
        "User-Agent": "MangoVoiceAssistant/1.0 (desktop globe; contact: local)",
        "Accept-Language": "en",
    }
    try:
        with httpx.Client(timeout=15.0, headers=headers) as client:
            r = client.get(
                _NOMINATIM,
                params={
                    "q": q,
                    "format": "json",
                    "limit": 1,
                },
            )
        if r.status_code >= 400:
            return f"Geocoding failed: HTTP {r.status_code}."
        rows = r.json()
        if not isinstance(rows, list) or not rows:
            return f"No map match for {q!r}. Try a different spelling."
        row = rows[0]
        lat = float(row.get("lat", 0))
        lng = float(row.get("lon", 0))
        disp = (row.get("display_name") or q).strip()
        bbox: dict[str, float] | None = None
        bb = row.get("boundingbox")
        if isinstance(bb, list) and len(bb) >= 4:
            try:
                south, north, west, east = float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])
                bbox = {"west": west, "south": south, "east": east, "north": north}
            except (TypeError, ValueError):
                bbox = None
        return (lat, lng, disp[:200], bbox)
    except Exception as exc:
        logger.warning("geocode failed", exc_info=True)
        return f"Geocoding error: {exc}"


def run(place: str) -> str:
    result = _geocode(place)
    if isinstance(result, str):
        return result
    lat, lng, disp, bbox = result
    url = build_globe_url(lat=lat, lng=lng, label=disp, bbox=bbox)
    zoom: float | None = None
    try:
        import re

        m = re.search(r"#map=(\d+)/", url)
        if m:
            zoom = float(m.group(1))
    except Exception:
        zoom = None
    if desktop_ipc.try_send_globe_url(url, label=disp, lat=lat, lng=lng, bbox=bbox, zoom=zoom):
        return f"Opened the map for {disp} in Mango."

    desktop_mode = (os.getenv("MANGO_DESKTOP", "").strip().lower() in {"1", "true", "yes", "on"})
    if desktop_mode:
        return f"Could not open the in-app map for {disp}."

    try:
        import webbrowser

        webbrowser.open(url)
    except Exception as exc:
        return f"Could not open globe window: {exc}"
    return f"Opened the globe for {disp} in your browser."

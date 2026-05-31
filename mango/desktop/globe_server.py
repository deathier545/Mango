"""Serve ``static/`` (``desktop.html``, ``globe.html``, …) on localhost for the map UI."""

from __future__ import annotations

import logging
import math
import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

_ZOOM_MAX = 18


def _lat_rad(lat: float) -> float:
    """Web-mercator latitude in radians (Mapbox-style fitBounds helper)."""
    sin_lat = math.sin(lat * math.pi / 180.0)
    rad_x2 = math.log((1.0 + sin_lat) / (1.0 - sin_lat)) / 2.0
    rad = max(min(rad_x2, math.pi), -math.pi) / 2.0
    return rad


def zoom_from_bbox(
    *,
    west: float,
    south: float,
    east: float,
    north: float,
    map_width_px: float = 1280.0,
    map_height_px: float = 720.0,
) -> int:
    """Pick an OSM-style integer zoom so the bbox fits a typical browser window."""
    world_dim = 256.0

    def zoom_dim(map_px: float, world_px: float, fraction: float) -> float:
        if fraction <= 0:
            return float(_ZOOM_MAX)
        return math.log2(map_px / world_px / fraction)

    lat_fraction = abs(_lat_rad(north) - _lat_rad(south)) / math.pi
    lng_diff = east - west
    if lng_diff < 0:
        lng_diff += 360.0
    lng_fraction = lng_diff / 360.0

    lat_zoom = zoom_dim(map_height_px, world_dim, lat_fraction)
    lng_zoom = zoom_dim(map_width_px, world_dim, lng_fraction)
    z = int(math.floor(min(lat_zoom, lng_zoom)))
    # One level wider so coastlines / labels are not flush against the edge.
    return max(2, min(_ZOOM_MAX, z - 1))

_server: ThreadingHTTPServer | None = None
_server_thread: threading.Thread | None = None
_port: int | None = None


def static_root() -> Path:
    return Path(__file__).resolve().parent / "static"


def get_serving_port() -> int:
    """Port for static files: parent's ``MANGO_GLOBE_PORT`` (desktop) or a local server."""
    raw = (os.environ.get("MANGO_GLOBE_PORT") or "").strip()
    if raw.isdigit():
        return int(raw)
    return ensure_running()


def ensure_running() -> int:
    """Start a background HTTP server if needed; return port bound to 127.0.0.1."""
    global _server, _server_thread, _port
    if _port is not None and _server_thread is not None and _server_thread.is_alive():
        return _port

    root = static_root()
    root.mkdir(parents=True, exist_ok=True)

    class _Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=str(root), **kwargs)

        def end_headers(self) -> None:
            try:
                path_only = self.path.split("?", 1)[0]
                if path_only.endswith(".html"):
                    self.send_header("Cache-Control", "no-store, max-age=0, must-revalidate")
            except Exception:
                pass
            super().end_headers()

        def log_message(self, fmt: str, *args: object) -> None:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(fmt, *args)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    _port = srv.server_address[1]
    _server = srv

    def serve() -> None:
        srv.serve_forever()

    _server_thread = threading.Thread(target=serve, daemon=True, name="MangoGlobeHTTP")
    _server_thread.start()
    logger.info("Globe static server on http://127.0.0.1:%s/", _port)
    return _port


def build_globe_url(
    *,
    lat: float,
    lng: float,
    label: str,
    bbox: dict[str, float] | None = None,
) -> str:
    """Browser URL that frames the place at a sensible zoom (OpenStreetMap ``#map=``)."""
    if bbox is not None:
        try:
            z = zoom_from_bbox(
                west=float(bbox["west"]),
                south=float(bbox["south"]),
                east=float(bbox["east"]),
                north=float(bbox["north"]),
            )
        except (KeyError, TypeError, ValueError):
            z = 6
    else:
        z = 6
    q = quote_plus(label)
    return (
        "https://www.openstreetmap.org/"
        f"?mlat={lat}&mlon={lng}&q={q}#map={z}/{lat}/{lng}"
    )

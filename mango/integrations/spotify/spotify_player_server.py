"""Local HTTP page for Spotify Web Playback SDK + Python Web API control."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

import mango.integrations.spotify.spotify_user_auth as sua

logger = logging.getLogger(__name__)

_HTML_PATH = Path(__file__).resolve().parent / "static" / "spotify_web_player.html"
_server: ThreadingHTTPServer | None = None
_server_thread: threading.Thread | None = None
_device_id: str | None = None
_device_ready = threading.Event()
_lock = threading.Lock()
_browser_opened = False
_manual_player_url_logged = False


def player_port() -> int:
    try:
        return int(os.getenv("MANGO_SPOTIFY_PLAYER_PORT", "9876").strip() or "9876")
    except ValueError:
        return 9876


def auto_open_player_browser() -> bool:
    """If true, first web play calls webbrowser.open on the local player URL (can surprise users)."""
    return os.getenv("MANGO_SPOTIFY_AUTO_OPEN_PLAYER", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def device_registration_timeout_s() -> float:
    """How long to wait for the browser SDK to POST device_id. Shorter when we do not auto-open a tab."""
    return 75.0 if auto_open_player_browser() else 18.0


def _is_loopback(addr: str) -> bool:
    return addr in ("127.0.0.1", "::1", "localhost")


def _read_html() -> bytes:
    if not _HTML_PATH.is_file():
        return b"<html><body>Missing spotify_web_player.html</body></html>"
    return _HTML_PATH.read_bytes()


def _api_track_uri(uri: str) -> str:
    u = uri.strip()
    if u.lower().endswith(":play"):
        u = u[:-5]
    return u


def ensure_server_started() -> tuple[bool, str]:
    """Start local player server if not running. Returns (ok, message)."""
    global _server, _server_thread
    with _lock:
        if _server is not None:
            return True, "Player server already running."
        port = player_port()
        try:

            class Handler(BaseHTTPRequestHandler):
                def log_message(self, fmt: str, *args: Any) -> None:
                    logger.debug("spotify player http %s", fmt % args)

                def _reject_remote(self) -> bool:
                    host = self.client_address[0]
                    if not _is_loopback(host):
                        self.send_response(403)
                        self.end_headers()
                        return True
                    return False

                def do_GET(self) -> None:  # noqa: N802
                    if self._reject_remote():
                        return
                    path = urlparse(self.path).path or "/"
                    if path in ("/", "/index.html"):
                        data = _read_html()
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        self.wfile.write(data)
                        return
                    if path == "/api/token":
                        tok = sua.get_valid_access_token()
                        self.send_response(200 if tok else 401)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        if tok:
                            self.wfile.write(
                                json.dumps({"access_token": tok}).encode("utf-8"),
                            )
                        else:
                            self.wfile.write(
                                json.dumps({"error": "not_logged_in"}).encode("utf-8"),
                            )
                        return
                    self.send_response(404)
                    self.end_headers()

                def do_POST(self) -> None:  # noqa: N802
                    global _device_id
                    if self._reject_remote():
                        return
                    path = urlparse(self.path).path or "/"
                    if path != "/api/device":
                        self.send_response(404)
                        self.end_headers()
                        return
                    ln = int(self.headers.get("Content-Length", "0") or 0)
                    raw = self.rfile.read(min(ln, 4096)) if ln > 0 else b"{}"
                    try:
                        body = json.loads(raw.decode("utf-8") or "{}")
                    except json.JSONDecodeError:
                        body = {}
                    did = body.get("device_id")
                    if isinstance(did, str) and did.strip():
                        _device_id = did.strip()
                        _device_ready.set()
                        logger.info("Spotify Web Playback device_id registered")
                    self.send_response(204)
                    self.end_headers()

            srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        except OSError as exc:
            return False, f"Could not bind player server on 127.0.0.1:{port}: {exc}"
        _server = srv

        def _run() -> None:
            try:
                srv.serve_forever(poll_interval=0.5)
            except Exception:
                logger.debug("player server stopped", exc_info=True)

        _server_thread = threading.Thread(
            target=_run,
            daemon=True,
            name="MangoSpotifyPlayerHTTP",
        )
        _server_thread.start()
        return True, f"Player server listening on http://127.0.0.1:{port}/"


def reset_player_browser_tab() -> None:
    """Allow webbrowser.open again (e.g. after logout)."""
    global _browser_opened, _manual_player_url_logged
    with _lock:
        _browser_opened = False
        _manual_player_url_logged = False


def open_player_tab_once() -> None:
    """Open default browser once (if enabled), or log the player URL once for manual opening."""
    global _browser_opened, _manual_player_url_logged
    url = f"http://127.0.0.1:{player_port()}/"
    with _lock:
        if auto_open_player_browser():
            if _browser_opened:
                return
            _browser_opened = True
        else:
            if _manual_player_url_logged:
                return
            _manual_player_url_logged = True
    if auto_open_player_browser():
        try:
            webbrowser.open(url)
            logger.info("Opened Spotify web player tab: %s", url)
        except Exception:
            logger.warning("webbrowser.open failed for player URL", exc_info=True)
    else:
        logger.info(
            "Spotify web playback: open this page in your browser once and leave the tab open: %s",
            url,
        )


def wait_for_device(timeout_s: float = 60.0) -> str | None:
    """Block until Web Playback posts device_id, or timeout (logs periodically so the host is not silent)."""
    remaining = float(timeout_s)
    while remaining > 0:
        chunk = min(5.0, remaining)
        if _device_ready.wait(timeout=chunk):
            return _device_id
        remaining -= chunk
        if not _device_ready.is_set():
            logger.info(
                "Waiting for Spotify web player tab at http://127.0.0.1:%s/ (~%.0fs left)...",
                player_port(),
                max(0.0, remaining),
            )
    return None


def reset_device_wait() -> None:
    _device_ready.clear()
    global _device_id
    _device_id = None


def current_device_id() -> str | None:
    return _device_id


def transfer_playback(access: str, device_id: str) -> bool:
    try:
        r = httpx.put(
            "https://api.spotify.com/v1/me/player",
            headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"},
            json={"device_ids": [device_id], "play": False},
            timeout=25.0,
        )
        ok = r.status_code in (200, 202, 204)
        if ok:
            time.sleep(0.25)
        return ok
    except httpx.HTTPError:
        logger.warning("transfer_playback failed", exc_info=True)
        return False


def play_uris(access: str, device_id: str, uris: list[str]) -> tuple[bool, str]:
    clean = [_api_track_uri(u) for u in uris if u.strip()]
    if not clean:
        return False, "No URIs to play."
    enc = urllib.parse.quote(device_id, safe="")
    try:
        r = httpx.put(
            f"https://api.spotify.com/v1/me/player/play?device_id={enc}",
            headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"},
            json={"uris": clean},
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        return False, f"Web API play request failed: {exc}"
    if r.status_code in (200, 204):
        return True, "Playing in your Spotify web player tab (browser audio)."
    if r.status_code == 403:
        return False, "Spotify refused playback (Premium required for Web Playback, or missing scopes)."
    if r.status_code == 404:
        return False, "No active device — open the Spotify web player tab (see logs for http://127.0.0.1:PORT/)."
    return False, f"Spotify Web API play HTTP {r.status_code}: {r.text[:300]}"


def toggle_play_pause(access: str) -> tuple[bool, str]:
    """Pause if playing, else resume (Web API)."""
    h = {"Authorization": f"Bearer {access}"}
    try:
        r = httpx.get(
            "https://api.spotify.com/v1/me/player",
            headers=h,
            timeout=20.0,
        )
    except httpx.HTTPError as exc:
        return False, str(exc)
    if r.status_code == 204:
        return False, "No active Spotify Web Playback session — open the Mango player browser tab."
    if r.status_code != 200:
        return False, f"GET player HTTP {r.status_code}: {r.text[:200]}"
    try:
        data = r.json()
    except Exception:
        return False, "Could not read playback state."
    if not isinstance(data, dict):
        return False, "Unexpected playback state."
    if bool(data.get("is_playing")):
        return web_api_transport(access, "pause")
    return web_api_transport(access, "resume")


def _device_id_query(device_id: str | None) -> str:
    if not device_id or not str(device_id).strip():
        return ""
    return "?" + urllib.parse.urlencode({"device_id": str(device_id).strip()})


def web_api_transport(access: str, action: str) -> tuple[bool, str]:
    """pause, resume, next, previous via Web API; pins device_id when known."""
    h = {"Authorization": f"Bearer {access}"}
    did = current_device_id()
    q = _device_id_query(did)
    try:
        if action == "pause":
            r = httpx.put(f"https://api.spotify.com/v1/me/player/pause{q}", headers=h, timeout=20.0)
        elif action == "resume":
            r = httpx.put(f"https://api.spotify.com/v1/me/player/play{q}", headers=h, timeout=20.0)
        elif action == "next":
            r = httpx.post(f"https://api.spotify.com/v1/me/player/next{q}", headers=h, timeout=20.0)
        elif action == "previous":
            r = httpx.post(f"https://api.spotify.com/v1/me/player/previous{q}", headers=h, timeout=20.0)
        else:
            return False, f"Unknown transport {action!r}"
    except httpx.HTTPError as exc:
        return False, str(exc)
    if r.status_code in (200, 202, 204):
        return True, "OK"
    return False, f"HTTP {r.status_code}: {r.text[:200]}"


def invalidate_device() -> None:
    """Clear Web Playback device (e.g. after 404 or user closed the tab)."""
    global _device_id
    _device_ready.clear()
    _device_id = None


def play_uri_via_web(access: str, launch_uri: str) -> tuple[bool, str]:
    """Ensure server, browser tab, device, transfer, play."""
    ok, msg = ensure_server_started()
    if not ok:
        return False, msg
    open_player_tab_once()
    wait_s = device_registration_timeout_s()
    if not _device_ready.is_set():
        did = wait_for_device(wait_s)
    else:
        did = current_device_id()
    if not did:
        return (
            False,
            "No Spotify web player device yet. Open "
            f"http://127.0.0.1:{player_port()}/ in your browser, log in if asked, click **Enable audio**, "
            "leave the tab open, then ask to play the song again. "
            f"(Waited {wait_s:.0f}s; set MANGO_SPOTIFY_AUTO_OPEN_PLAYER=1 if you want Mango to open this URL for you.)",
        )
    transfer_playback(access, did)
    ok2, msg2 = play_uris(access, did, [launch_uri])
    if not ok2 and ("404" in msg2 or "No active" in msg2):
        invalidate_device()
    return ok2, msg2

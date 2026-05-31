"""Spotify user OAuth (PKCE) + token storage for Web API / Web Playback."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import httpx

from mango.retry_utils import retry_call
from mango.timeouts import HTTP_LONG_S

logger = logging.getLogger(__name__)

_TOKEN_PATH = Path.home() / ".mango" / "spotify_user_token.json"
_SCOPES = (
    "streaming user-read-email user-read-private "
    "user-modify-playback-state user-read-playback-state"
)


def _client_id() -> str:
    return (
        os.getenv("MANGO_SPOTIFY_CLIENT_ID", "").strip()
        or os.getenv("SPOTIFY_CLIENT_ID", "").strip()
    )


def _client_secret() -> str:
    return (
        os.getenv("MANGO_SPOTIFY_CLIENT_SECRET", "").strip()
        or os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()
    )


def redirect_uri() -> str:
    return os.getenv(
        "MANGO_SPOTIFY_REDIRECT_URI",
        "http://127.0.0.1:8765/callback",
    ).strip()


def oauth_listen_port() -> int:
    u = redirect_uri()
    try:
        parsed = urllib.parse.urlparse(u)
        if parsed.port:
            return int(parsed.port)
    except Exception:
        pass
    return 8765


def _token_path() -> Path:
    raw = os.getenv("MANGO_SPOTIFY_USER_TOKEN_PATH", "").strip()
    return Path(raw).expanduser() if raw else _TOKEN_PATH


def load_token_data() -> dict[str, Any] | None:
    p = _token_path()
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        logger.warning("Could not read %s", p, exc_info=True)
        return None


def save_token_data(data: dict[str, Any]) -> None:
    p = _token_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(p)


def delete_token_data() -> None:
    p = _token_path()
    try:
        if p.is_file():
            p.unlink()
    except OSError:
        pass


def _pkce_pair() -> tuple[str, str]:
    """Return (verifier, challenge) per RFC 7636; verifier length 64–96 chars URL-safe."""
    v = secrets.token_urlsafe(72)
    v = v[:96]
    digest = hashlib.sha256(v.encode("ascii")).digest()
    ch = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return v, ch


def _exchange_code(code: str, verifier: str) -> dict[str, Any] | None:
    cid = _client_id()
    if not cid:
        return None
    body = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri(),
        "client_id": cid,
        "code_verifier": verifier,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    secret = _client_secret()
    if secret:
        body["client_secret"] = secret
    try:
        r = retry_call(
            lambda: httpx.post(
                "https://accounts.spotify.com/api/token",
                data=body,
                headers=headers,
                timeout=HTTP_LONG_S,
            ),
            attempts=3,
            base_delay_s=0.5,
            retry_on=(httpx.TransportError,),
            retry_if_result=lambda resp: resp.status_code in (429, 500, 502, 503, 504),
            label="spotify_exchange_code",
        )
    except httpx.HTTPError as exc:
        logger.warning("Spotify token exchange failed: %s", exc)
        return None
    if r.status_code != 200:
        logger.warning("Spotify token exchange HTTP %s: %s", r.status_code, r.text[:500])
        return None
    data = r.json()
    return data if isinstance(data, dict) else None


def refresh_access_token() -> dict[str, Any] | None:
    """Return new token bundle (includes access_token, refresh_token, expires_at) or None."""
    cur = load_token_data()
    if not cur or not isinstance(cur.get("refresh_token"), str):
        return None
    cid = _client_id()
    if not cid:
        return None
    body = {
        "grant_type": "refresh_token",
        "refresh_token": cur["refresh_token"],
        "client_id": cid,
    }
    secret = _client_secret()
    if secret:
        body["client_secret"] = secret
    try:
        r = retry_call(
            lambda: httpx.post(
                "https://accounts.spotify.com/api/token",
                data=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=HTTP_LONG_S,
            ),
            attempts=3,
            base_delay_s=0.5,
            retry_on=(httpx.TransportError,),
            retry_if_result=lambda resp: resp.status_code in (429, 500, 502, 503, 504),
            label="spotify_refresh_token",
        )
    except httpx.HTTPError as exc:
        logger.warning("Spotify refresh failed: %s", exc)
        return None
    if r.status_code != 200:
        logger.warning("Spotify refresh HTTP %s: %s", r.status_code, r.text[:400])
        return None
    data = r.json()
    if not isinstance(data, dict):
        return None
    # Spotify may omit refresh_token on refresh — keep old one
    if "refresh_token" not in data and isinstance(cur.get("refresh_token"), str):
        data["refresh_token"] = cur["refresh_token"]
    exp = int(time.time()) + int(data.get("expires_in", 3600))
    data["expires_at"] = exp
    save_token_data(data)
    return data


def get_valid_access_token() -> str | None:
    """Return a non-expired access token, refreshing when possible."""
    data = load_token_data()
    if not data or not isinstance(data.get("access_token"), str):
        return None
    exp = int(data.get("expires_at", 0))
    if exp > int(time.time()) + 45:
        return str(data["access_token"])
    refreshed = refresh_access_token()
    if refreshed and isinstance(refreshed.get("access_token"), str):
        return str(refreshed["access_token"])
    return None


def run_login_flow(*, timeout_s: float = 300.0) -> str:
    """Open browser for Spotify login; wait for redirect with ?code=. Returns user-facing message."""
    cid = _client_id()
    if not cid:
        return "Missing MANGO_SPOTIFY_CLIENT_ID (or SPOTIFY_CLIENT_ID) in the environment."
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(16)
    params = {
        "response_type": "code",
        "client_id": cid,
        "scope": _SCOPES,
        "redirect_uri": redirect_uri(),
        "state": state,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "show_dialog": "true",
    }
    auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(
        params,
        quote_via=urllib.parse.quote,
    )

    result: dict[str, Any] = {"code": None, "err": None, "state_ok": False}
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            logger.debug("oauth %s", fmt % args)

        def do_GET(self) -> None:  # noqa: N802
            if self.path.startswith("/favicon"):
                self.send_response(404)
                self.end_headers()
                return
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path.rstrip("/") not in ("/callback", "/"):
                self.send_response(404)
                self.end_headers()
                return
            qs = urllib.parse.parse_qs(parsed.query or "")
            if qs.get("error"):
                result["err"] = qs.get("error", [""])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h2>Spotify login failed</h2>"
                    b"<p>You can close this tab.</p></body></html>",
                )
                done.set()
                return
            code_l = qs.get("code", [])
            st_l = qs.get("state", [])
            if not code_l:
                result["err"] = "missing_code"
                self.send_response(400)
                self.end_headers()
                done.set()
                return
            if not st_l or st_l[0] != state:
                result["err"] = "bad_state"
                self.send_response(400)
                self.end_headers()
                done.set()
                return
            result["code"] = code_l[0]
            result["state_ok"] = True
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>Mango: Spotify connected</h2>"
                b"<p>You can close this tab and return to Mango.</p></body></html>",
            )
            done.set()

    port = oauth_listen_port()
    server = HTTPServer(("127.0.0.1", port), Handler)
    th = threading.Thread(target=server.serve_forever, daemon=True, name="SpotifyOAuth")
    th.start()
    try:
        webbrowser.open(auth_url)
        if not done.wait(timeout=timeout_s):
            return "Login timed out waiting for Spotify redirect. Check redirect URI in the Spotify dashboard."
    finally:
        try:
            server.shutdown()
        except Exception:
            pass
        try:
            server.server_close()
        except Exception:
            pass

    if result.get("err"):
        return f"Spotify login error: {result['err']}"
    code = result.get("code")
    if not isinstance(code, str):
        return "Spotify login did not return an authorization code."

    tok = _exchange_code(code, verifier)
    if not tok or not isinstance(tok.get("access_token"), str):
        return "Spotify token exchange failed (check client id / redirect URI / client secret if your app requires it)."
    exp = int(time.time()) + int(tok.get("expires_in", 3600))
    bundle = {
        "access_token": tok["access_token"],
        "token_type": tok.get("token_type", "Bearer"),
        "expires_at": exp,
        "scope": tok.get("scope", ""),
    }
    if isinstance(tok.get("refresh_token"), str):
        bundle["refresh_token"] = tok["refresh_token"]
    save_token_data(bundle)
    return "Spotify login saved. Web playback is ready (open the Mango player tab if prompted)."


def status_line() -> str:
    d = load_token_data()
    if not d:
        return "No Spotify user login on file. Use spotify_session action=login."
    if not isinstance(d.get("refresh_token"), str):
        return "Incomplete token file (missing refresh_token). Run login again."
    tok = get_valid_access_token()
    if not tok:
        return "Spotify tokens present but refresh failed. Run login again."
    return "Spotify user login OK (access token usable)."

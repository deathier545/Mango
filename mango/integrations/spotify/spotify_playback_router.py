"""Higher-level Spotify playback routing (web player + desktop connect)."""

from __future__ import annotations

import logging
from typing import Any

from mango.integration_services import SpotifyAuthService, SpotifyDesktopPlaybackService

logger = logging.getLogger(__name__)


def try_web_playback(
    *,
    launch_uri: str,
    query_label: str,
    track_obj: dict[str, Any] | None,
    force_spotify_app: bool,
    web_playback_enabled: bool,
    track_meta_line: Any,
) -> str | None:
    """Return user-facing message when web playback path handles the request, else None."""
    if not web_playback_enabled or force_spotify_app:
        return None

    import mango.integrations.spotify.spotify_player_server as sps
    from mango.integration_services import SpotifyUserAuthService

    auth_service = SpotifyUserAuthService()
    uat = auth_service.get_valid_access_token()
    if not uat:
        return (
            "Web playback is on (MANGO_SPOTIFY_WEB_PLAYBACK) but Spotify user login is missing. "
            "Use spotify_session with action login, or set MANGO_SPOTIFY_WEB_PLAYBACK=0 to use the desktop app."
        )
    ok_web, web_msg = sps.play_uri_via_web(uat, launch_uri)
    if ok_web:
        meta = track_meta_line(track_obj) if isinstance(track_obj, dict) else query_label
        logger.info("spotify_play web_playback ok")
        return (
            f"Playing in your browser’s Spotify web player: {meta!r}. {web_msg} "
            f"If you hear nothing, open http://127.0.0.1:{sps.player_port()}/ "
            "and click **Enable audio** once (Chrome/Edge autoplay). "
            "Sound comes from the browser, not Mango’s voice output."
        )
    return (
        f"Web playback failed: {web_msg} "
        f"Open http://127.0.0.1:{sps.player_port()}/ in your browser, keep the tab open, "
        "click **Enable audio** if the page asks, and ensure Spotify Premium + login completed. "
        "Set MANGO_SPOTIFY_AUTO_OPEN_PLAYER=1 if you want Mango to auto-open that page in your browser."
    )


def try_desktop_connect_playback(
    *,
    launch_uri: str,
    query_label: str,
    track_obj: dict[str, Any] | None,
    extra_suffix: str,
    force_spotify_app: bool,
    web_playback_enabled: bool,
    track_meta_line: Any,
    auth_service: SpotifyAuthService,
    desktop_service: SpotifyDesktopPlaybackService,
) -> str | None:
    """Try Spotify Connect desktop playback and return message on success, otherwise None."""
    if web_playback_enabled or force_spotify_app or not desktop_service.enabled():
        return None

    import mango.integrations.spotify.spotify_windows_ui as swu

    uat = auth_service.get_valid_access_token()
    if not uat:
        return None
    if swu.track_change_window_cycle_enabled():
        swu.foreground_spotify_windows()
    ok_api, msg_api = desktop_service.play_track_uri(uat, launch_uri)
    if ok_api:
        if swu.track_change_window_cycle_enabled():
            swu.pause_then_minimize_spotify()
        meta = track_meta_line(track_obj) if isinstance(track_obj, dict) else query_label
        logger.info("spotify_play desktop_connect ok")
        return (
            f"Playing on Spotify via Connect (Web API, avoids URI pop-ups): {meta!r}. "
            f"{msg_api}{extra_suffix}"
        )
    logger.info("spotify_play desktop_connect failed, falling back to URI: %s", msg_api)
    return None

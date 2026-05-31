"""Resolve a song to Spotify, then play a short preview in Mango or open the Spotify app."""

from __future__ import annotations

import logging
import os
import sys
import urllib.parse
from typing import Any

import httpx

import mango.integrations.spotify.spotify_playback_router as spr
import mango.integrations.spotify.spotify_track_resolver as sres
import mango.integrations.spotify.spotify_uri_launcher as suri
from mango.integration_services import SpotifyDesktopApiService, SpotifyUserAuthService
from mango.integrations.discord.discord_music_sync import try_start_discord_music_stream
from mango.integrations.spotify.spotify_auto_close import schedule_close_when_track_ends

logger = logging.getLogger(__name__)

DESCRIPTION = (
    "Play music from Spotify’s catalog. **Default (MANGO_SPOTIFY_WEB_PLAYBACK off):** after **spotify_session** login, "
    "Mango first tries **Spotify Connect (Web API)** on your **Computer** device (**MANGO_SPOTIFY_DESKTOP_API**, default on) "
    "so the queue changes **without** a `spotify:` URI / window handoff; on Windows with **MANGO_SPOTIFY_MINIMIZED** (default), "
    "Mango **foregrounds Spotify briefly**, applies the Connect change, **then minimizes** again. If Connect fails it falls back to **Spotify.exe** "
    "with the same **open → play → minimize** pattern. "
    "Do **not** call **open_app(spotify)** in the same turn unless the user only asked to open the app without a song — "
    "**spotify_play** already launches Spotify when needed. "
    "Use **spotify_transport** for pause / skip / previous (**Windows media keys**; Spotify should be the active media session). "
    "With **MANGO_SPOTIFY_WEB_PLAYBACK=1** + **spotify_session** login, uses **browser Web Playback** instead (no desktop handoff). "
    "API search skips obvious **instrumental / karaoke / backing-track** titles when **MANGO_SPOTIFY_PREFER_VOCALS=1** (default) "
    "and matches **artist names** from the user's words (not unrelated songs whose title mentions the artist). "
    "For 'a song by Artist' with no title, picks that artist's top track. "
    "On Windows, **closes Spotify then reopens** on each new track by default (**MANGO_SPOTIFY_RESTART_ON_PLAY**), "
    "and **closes Spotify when that track finishes** (**MANGO_SPOTIFY_CLOSE_WHEN_DONE**, needs user login for accurate timing). "
    "API credentials improve search accuracy."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": (
                "Song to play or a Spotify URI, e.g. \"The Less I Know The Better\", "
                "\"Queen Bohemian Rhapsody\", or spotify:track:…"
            ),
        },
    },
    "required": ["query"],
    "additionalProperties": False,
}


# Behavior flags
def _force_spotify_app() -> bool:
    return os.getenv("MANGO_SPOTIFY_FORCE_APP", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _inline_preview_enabled() -> bool:
    """When True, prefer Spotify's ~30s preview inside Mango (no desktop queue change). Default: off."""
    return os.getenv("MANGO_SPOTIFY_INLINE_PREVIEW", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _api_access_token() -> str | None:
    return sres.api_access_token()


def _api_search_tracks(token: str, query: str, *, limit: int = 15) -> list[dict[str, Any]]:
    return sres.api_search_tracks(token, query, limit=limit)


def _track_text_blob(track: dict[str, Any]) -> str:
    return sres.track_text_blob(track)


def _likely_instrumental_or_karaoke(track: dict[str, Any]) -> bool:
    return sres.likely_instrumental_or_karaoke(track)


def _prefer_non_instrumental_search() -> bool:
    return sres.prefer_non_instrumental_search()


def _api_search_best_track(token: str, query: str) -> dict[str, Any] | None:
    return sres.api_search_best_track(token, query)


def _api_get_track(token: str, track_id: str) -> dict[str, Any] | None:
    return sres.api_get_track(token, track_id)


def _track_id_from_spotify_uri(uri: str) -> str | None:
    return sres.track_id_from_spotify_uri(uri)


def _track_ids_from_ddgs(query: str, *, max_ids: int = 10) -> list[str]:
    return sres.track_ids_from_ddgs(query, max_ids=max_ids)


def _try_play_preview(preview_url: str) -> bool:
    """Download short preview MP3 and play through Mango’s pygame path (no Spotify app)."""
    try:
        r = httpx.get(preview_url, timeout=35.0, follow_redirects=True)
        if r.status_code != 200 or not r.content:
            logger.warning("preview GET failed status=%s len=%s", r.status_code, len(r.content or b""))
            return False
        from mango.audio import play_mp3_bytes

        play_mp3_bytes(r.content, interrupt_check=None, audio_reset=True, hud_level_out=None)
        return True
    except Exception:
        logger.warning("inline preview playback failed", exc_info=True)
        return False


# Compatibility test seam: tests reference this helper directly.
def _spotify_exe_windows() -> str | None:
    # Canonical implementation lives in mango.integrations.spotify.spotify_uri_launcher.
    return suri.spotify_exe_windows()


def _launch_uri(uri: str) -> None:
    suri.launch_uri(uri)


def _track_meta_line(track: dict[str, Any]) -> str:
    name = str(track.get("name") or "track")
    arts = track.get("artists")
    if isinstance(arts, list) and arts:
        a0 = arts[0]
        if isinstance(a0, dict) and a0.get("name"):
            return f"{name} — {a0['name']}"
    return name


def _schedule_auto_close_after_play(
    track_uri: str | None,
    track_obj: dict[str, Any] | None,
) -> None:
    if _web_playback_enabled() or _inline_preview_enabled():
        return
    tok: str | None = None
    try:
        tok = SpotifyUserAuthService().get_valid_access_token()
    except Exception:
        logger.debug("auto-close: no user token", exc_info=True)
    schedule_close_when_track_ends(
        track_uri=track_uri,
        track_obj=track_obj,
        access_token=tok,
    )


def _spotify_result_message(base: str, *, query: str, track_obj: dict[str, Any] | None) -> str:
    """Append exact track identity so the LLM does not invent titles."""
    meta = _track_meta_line(track_obj) if isinstance(track_obj, dict) else None
    parts = [base.strip()]
    if meta:
        parts.append(f"TRACK_PLAYED: {meta!r} (your search was {query!r}).")
    else:
        parts.append(f"SEARCH_QUERY: {query!r}.")
    discord_note = try_start_discord_music_stream()
    if discord_note:
        parts.append(discord_note)
        parts.append(
            "Reminder: Spotify output should be `CABLE Input` so friends hear it in Discord."
        )
    return " ".join(parts)


def _web_playback_enabled() -> bool:
    return os.getenv("MANGO_SPOTIFY_WEB_PLAYBACK", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _uri_for_desktop_playback(uri: str) -> str:
    return suri.uri_for_desktop_playback(uri)


def _spotify_exe_uri_param(uri: str) -> str:
    return suri.spotify_exe_uri_param(uri)


def run(query: str) -> str:
    q = (query or "").strip()
    if not q:
        return "Error: query is empty — pass a song name or spotify: URI."

    tok = _api_access_token()
    track_obj: dict[str, Any] | None = None
    uri: str | None = None
    via = ""

    ql = q.lower()
    if ql.startswith("spotify:"):
        uri = q
        tid = _track_id_from_spotify_uri(q)
        if tid and tok:
            track_obj = _api_get_track(tok, tid)
        if not track_obj and tid:
            uri = f"spotify:track:{tid}"
    else:
        if tok:
            track_obj = _api_search_best_track(tok, q)
            if track_obj:
                u = track_obj.get("uri")
                uri = u if isinstance(u, str) and u.startswith("spotify:track:") else None
                via = "spotify_api"
        if not uri:
            for tid in _track_ids_from_ddgs(q):
                cand_uri = f"spotify:track:{tid}"
                if tok:
                    cand = _api_get_track(tok, tid)
                    if isinstance(cand, dict) and _prefer_non_instrumental_search():
                        if _likely_instrumental_or_karaoke(cand):
                            continue
                    uri = cand_uri
                    track_obj = cand if isinstance(cand, dict) else None
                else:
                    uri = cand_uri
                    track_obj = None
                via = "web_lookup"
                break

    preview_url = None
    if isinstance(track_obj, dict):
        pu = track_obj.get("preview_url")
        if isinstance(pu, str) and pu.startswith("http"):
            preview_url = pu

    if not uri and not ql.startswith("spotify:"):
        uri = "spotify:search:" + urllib.parse.quote(q, safe="")
        via = "search_only"
        try:
            _launch_uri(uri)
        except OSError as exc:
            return f"Error sending to Spotify: {exc}"
        return (
            f"Opened Spotify search for {q!r}. Full tracks require the Spotify app. "
            "For inline short previews when available, set MANGO_SPOTIFY_CLIENT_ID/SECRET and use a track "
            "that still has a preview clip from Spotify."
        )

    assert uri is not None

    if sys.platform == "win32":
        import mango.integrations.spotify.spotify_windows_ui as swu

        if swu.restart_on_new_track_enabled() and not _web_playback_enabled():
            swu.restart_spotify_for_new_track()

    launch_uri = _uri_for_desktop_playback(uri)

    if (
        preview_url
        and _inline_preview_enabled()
        and not _force_spotify_app()
    ):
        if _try_play_preview(preview_url):
            meta = _track_meta_line(track_obj) if isinstance(track_obj, dict) else q
            logger.info("spotify_play inline preview ok via=%s", via or "uri")
            return _spotify_result_message(
                (
                    f"Played Spotify’s short preview in Mango for {meta!r} (~30s max). "
                    "The Spotify app was not told to switch tracks — set MANGO_SPOTIFY_INLINE_PREVIEW=0 (default) "
                    "or use MANGO_SPOTIFY_FORCE_APP=1 to open Spotify for full playback."
                ),
                query=q,
                track_obj=track_obj,
            )

    web_msg = spr.try_web_playback(
        launch_uri=launch_uri,
        query_label=q,
        track_obj=track_obj if isinstance(track_obj, dict) else None,
        force_spotify_app=_force_spotify_app(),
        web_playback_enabled=_web_playback_enabled(),
        track_meta_line=_track_meta_line,
    )
    if web_msg is not None:
        return _spotify_result_message(web_msg, query=q, track_obj=track_obj)

    extra = ""
    if preview_url and _force_spotify_app():
        extra = " (MANGO_SPOTIFY_FORCE_APP skips inline preview.)"
    elif not preview_url and tok:
        extra = (
            " Spotify no longer exposes a preview clip for this track — only the app can play the full song."
        )

    desktop_msg = spr.try_desktop_connect_playback(
        launch_uri=launch_uri,
        query_label=q,
        track_obj=track_obj if isinstance(track_obj, dict) else None,
        extra_suffix=extra,
        force_spotify_app=_force_spotify_app(),
        web_playback_enabled=_web_playback_enabled(),
        track_meta_line=_track_meta_line,
        auth_service=SpotifyUserAuthService(),
        desktop_service=SpotifyDesktopApiService(),
    )
    if desktop_msg is not None:
        logger.info("spotify_play desktop_connect ok via=%s", via or "uri")
        _schedule_auto_close_after_play(uri, track_obj)
        return _spotify_result_message(desktop_msg, query=q, track_obj=track_obj)

    try:
        _launch_uri(launch_uri)
    except OSError as exc:
        logger.warning("spotify_play failed: %s", exc, exc_info=True)
        return f"Error sending to Spotify: {exc}"

    logger.info(
        "spotify_play launched app uri=%r via=%s had_preview=%s",
        launch_uri[:120],
        via,
        bool(preview_url),
    )
    _schedule_auto_close_after_play(uri, track_obj)
    if via == "spotify_api":
        return _spotify_result_message(
            f"Opened Spotify for: {launch_uri}.{extra}", query=q, track_obj=track_obj
        )
    if via == "web_lookup":
        return _spotify_result_message(
            f"Opened Spotify for: {launch_uri}.{extra}", query=q, track_obj=track_obj
        )
    return _spotify_result_message(
        f"Opened Spotify: {launch_uri[:220]}{'…' if len(launch_uri) > 220 else ''}.{extra}",
        query=q,
        track_obj=track_obj,
    )

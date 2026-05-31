"""Desktop tool: talk to the running Discord voice bridge over localhost (see ``discord_voice_control``)."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from mango.integrations.discord.discord_bridge_launcher import (
    auto_start_enabled,
    ensure_discord_bridge_running,
)
from mango.integrations.discord.discord_voice_client import (
    CONTROL_HEADER,
    control_port,
    control_secret,
)

logger = logging.getLogger(__name__)

_DESCRIPTION_TEMPLATE = (
    "Use when the user wants Mango’s **Discord voice bridge** to find a **small voice chat** "
    "(a few people — not a huge public channel), join it, or nudge friends. The bridge runs on "
    "discord.py-self as a **user account selfbot**, so it can join server voice channels, 1:1 DM calls, "
    "**and** group-DM calls. **Hearing the user** is always the **desktop microphone** (PTT / always-listen); "
    "this tool does **not** turn other people’s Discord audio into STT. The bridge only **sends TTS into** "
    "Discord (after join: `!say`, HTTP `POST /v1/voice/speak`, or optional `MANGO_DISCORD_AUTO_SYNC_ON_READY`). "
    "It can also start/stop streaming Spotify/system audio from VB-CABLE (`CABLE Output`) into the call when "
    "Spotify is set to output to `CABLE Input`. "
    "**Always call this tool** when they ask for Discord voice status, to start the bridge, or to join/sync. "
    "If the bridge process is off, this tool **starts it automatically** on this PC (action **ensure_bridge** "
    "or any other action) — do not tell __OWNER__ to open a separate terminal unless auto-start fails. "
    "`MANGO_DISCORD_CONTROL_SECRET` is optional. "
    "`MANGO_DISCORD_OWNER_USER_ID` is optional (defaults to the selfbot account itself). "
    "**status** lists active sessions; **sync** joins __OWNER_POS__ current call when it matches size limits, "
    "and only joins a different call if `allow_join_other_sessions` is true because __OWNER__ explicitly asked. "
    "It may ping optional friend ids in `MANGO_DISCORD_NOTIFY_CHANNEL_ID` "
    "and can open the Discord desktop app. **who_in_call** summarizes known people currently in call. "
    "**greet_everyone** greets known people in the call other than __OWNER__ by name. "
    "**say_to_person** speaks a short message to a known person currently in call. "
    "**leave** disconnects from Discord voice. **music_start/music_resume** stream the configured "
    "Windows audio capture device into Discord voice; **music_stop/music_pause** stop that stream."
)


def _possessive_phrase(owner: str) -> str:
    o = (owner or "the owner").strip() or "the owner"
    if o.casefold() == "you":
        return "your"
    return f"{o}'s"


def description_for(owner: str) -> str:
    """Tool description with the configured owner display name (see MANGO_OWNER_NAME)."""
    o = (owner or "the owner").strip() or "the owner"
    pos = _possessive_phrase(o)
    return _DESCRIPTION_TEMPLATE.replace("__OWNER__", o).replace("__OWNER_POS__", pos)


# Default for imports/tests; runtime uses ``description_for`` from ``ToolRegistry``.
DESCRIPTION = description_for("the owner")

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "ensure_bridge",
                "status",
                "sync",
                "who_in_call",
                "greet_everyone",
                "say_to_person",
                "leave",
                "music_start",
                "music_pause",
                "music_resume",
                "music_stop",
            ],
            "description": (
                "ensure_bridge = start the Discord voice bridge process on this PC if it is not running "
                "(use when they ask to start the bridge); status = list active voice sessions; sync = join "
                "the best matching small call or fall back to pings / open Discord; who_in_call = summarize "
                "current call roster; greet_everyone = say hello to known guests; say_to_person = speak to "
                "one person; leave = disconnect; music_start/resume = stream capture device into the call; "
                "music_pause/stop = stop that stream."
            ),
        },
        "target_name": {
            "type": "string",
            "description": "For say_to_person: known person name/username, e.g. Ariana, Brooke, lovee_ariana, .brook.e, or her when unambiguous.",
        },
        "message": {
            "type": "string",
            "description": "For say_to_person: short message to speak to the target. If omitted, says hello.",
        },
        "music_device": {
            "type": "string",
            "description": (
                "Optional FFmpeg DirectShow audio device name for music_start. Defaults to "
                "`CABLE Output (VB-Audio Virtual Cable)` or MANGO_DISCORD_MUSIC_DEVICE."
            ),
        },
        "only_small_group_calls": {
            "type": "boolean",
            "description": "If true, only consider channels with at most max_humans_in_channel humans (default true).",
        },
        "min_humans_in_channel": {
            "type": "integer",
            "minimum": 1,
            "maximum": 50,
            "description": "Require at least this many humans in the channel (default 2 = you plus at least one other). Use 1 to allow solo VCs.",
        },
        "max_humans_in_channel": {
            "type": "integer",
            "minimum": 2,
            "maximum": 99,
            "description": "With only_small_group_calls, cap channel size (default 4).",
        },
        "ping_friend_user_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional Discord snowflake strings to @mention when sync finds no qualifying VC and MANGO_DISCORD_NOTIFY_CHANNEL_ID is set.",
        },
        "open_discord_desktop_if_none": {
            "type": "boolean",
            "description": "If true and no session was joined, launch the Discord desktop app (same as open_app discord).",
        },
        "allow_join_other_sessions": {
            "type": "boolean",
            "description": (
                "If true, sync may join the smallest qualifying call even when the primary user is not already in it. "
                "Use only when they explicitly ask to join another/available call."
            ),
        },
    },
    "required": ["action"],
    "additionalProperties": False,
}


def _format_payload(data: dict[str, Any]) -> str:
    lines = data.get("lines")
    if isinstance(lines, list):
        return "\n".join(str(x) for x in lines)
    err = data.get("error") or data.get("detail")
    if err:
        return f"Discord voice control: {err}"
    return str(data)


def _bridge_unreachable_message(port: int) -> str:
    return (
        f"No voice control HTTP server on port {port}. "
        "Bridge auto-start may still be in progress or failed — check logs/discord-voice.err.log."
    )


def _control_timeout_seconds() -> float:
    raw = os.getenv("MANGO_DISCORD_CONTROL_TIMEOUT_S", "").strip()
    if not raw:
        return 60.0
    try:
        return max(5.0, min(float(raw), 120.0))
    except ValueError:
        logger.warning("Invalid MANGO_DISCORD_CONTROL_TIMEOUT_S=%r — using default 60s", raw)
        return 60.0


def _request_http(
    action: str,
    *,
    only_small_group_calls: bool,
    min_humans_in_channel: int,
    max_humans_in_channel: int,
    ping_friend_user_ids: list[str] | None,
    open_discord_desktop_if_none: bool,
    allow_join_other_sessions: bool,
    music_device: str | None,
    target_name: str | None,
    message: str | None,
    control_timeout_s: float,
) -> str:
    secret = control_secret()
    action = (action or "").strip().lower()
    port = control_port()
    base = f"http://127.0.0.1:{port}"
    headers: dict[str, str] = {}
    if secret:
        headers[CONTROL_HEADER] = secret

    with httpx.Client(timeout=control_timeout_s) as client:
        if action == "status":
            r = client.get(f"{base}/v1/voice/status", headers=headers)
        elif action == "who_in_call":
            r = client.post(f"{base}/v1/voice/who", headers=headers, json={})
        elif action == "sync":
            body: dict[str, Any] = {
                "only_small_group_calls": only_small_group_calls,
                "min_humans_in_channel": min_humans_in_channel,
                "max_humans_in_channel": max_humans_in_channel,
                "open_discord_desktop_if_none": open_discord_desktop_if_none,
                "allow_join_other_sessions": allow_join_other_sessions,
            }
            if ping_friend_user_ids:
                body["ping_friend_user_ids"] = list(ping_friend_user_ids)
            r = client.post(f"{base}/v1/voice/sync", headers=headers, json=body)
        elif action == "leave":
            r = client.post(f"{base}/v1/voice/leave", headers=headers, json={})
        elif action == "greet_everyone":
            r = client.post(f"{base}/v1/voice/greet", headers=headers, json={})
        elif action == "say_to_person":
            r = client.post(
                f"{base}/v1/voice/say-to",
                headers=headers,
                json={"target": target_name or "", "message": message or ""},
            )
        elif action in ("music_start", "music_resume"):
            body = {}
            if music_device:
                body["device"] = music_device
            r = client.post(f"{base}/v1/voice/music/start", headers=headers, json=body)
        elif action in ("music_stop", "music_pause"):
            r = client.post(f"{base}/v1/voice/music/stop", headers=headers, json={})
        else:
            return (
                f"Unknown action {action!r}; use ensure_bridge, status, sync, who_in_call, "
                "greet_everyone, say_to_person, leave, music_start/resume, or music_pause/stop."
            )

        if r.status_code == 401:
            return "Discord voice control rejected the secret (check MANGO_DISCORD_CONTROL_SECRET matches the bridge)."
        if r.status_code == 404:
            return _bridge_unreachable_message(port)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict):
            return _format_payload(data)
        return str(data)


def _needs_bridge_start(result: str) -> bool:
    t = (result or "").casefold()
    return (
        "not reachable" in t
        or "no voice control http" in t
        or "bridge auto-start" in t
        or "nothing listening" in t
    )


def run(
    action: str,
    *,
    only_small_group_calls: bool = True,
    min_humans_in_channel: int = 2,
    max_humans_in_channel: int = 4,
    ping_friend_user_ids: list[str] | None = None,
    open_discord_desktop_if_none: bool = False,
    allow_join_other_sessions: bool = False,
    music_device: str | None = None,
    target_name: str | None = None,
    message: str | None = None,
    _host_control_timeout_s: float | None = None,
    _host_bridge_wait_seconds: float | None = None,
    _host_bridge_poll_interval_s: float | None = None,
) -> str:
    action = (action or "").strip().lower()
    control_timeout_s = (
        _control_timeout_seconds()
        if _host_control_timeout_s is None
        else max(5.0, min(float(_host_control_timeout_s), 120.0))
    )
    bridge_wait_seconds = (
        90.0
        if _host_bridge_wait_seconds is None
        else max(10.0, min(float(_host_bridge_wait_seconds), 120.0))
    )
    bridge_poll_interval_s = (
        None
        if _host_bridge_poll_interval_s is None
        else max(0.25, min(float(_host_bridge_poll_interval_s), 5.0))
    )

    if action == "ensure_bridge":
        ok, msg = ensure_discord_bridge_running(
            wait_seconds=bridge_wait_seconds,
            poll_interval=bridge_poll_interval_s,
        )
        return msg if ok else f"BRIDGE_START_FAILED: {msg}"

    try:
        result = _request_http(
            action,
            only_small_group_calls=only_small_group_calls,
            min_humans_in_channel=min_humans_in_channel,
            max_humans_in_channel=max_humans_in_channel,
            ping_friend_user_ids=ping_friend_user_ids,
            open_discord_desktop_if_none=open_discord_desktop_if_none,
            allow_join_other_sessions=allow_join_other_sessions,
            music_device=music_device,
            target_name=target_name,
            message=message,
            control_timeout_s=control_timeout_s,
        )
    except httpx.ConnectError:
        result = (
            "Discord voice bridge is not reachable on this PC (nothing listening on localhost)."
        )
    except httpx.HTTPError as exc:
        logger.warning("discord_voice http error: %s", exc)
        return f"Discord voice control HTTP error: {exc}"
    except Exception as exc:
        logger.exception("discord_voice tool")
        return f"Discord voice tool error: {exc}"

    if _needs_bridge_start(result) and auto_start_enabled():
        ok, start_msg = ensure_discord_bridge_running(
            wait_seconds=bridge_wait_seconds,
            poll_interval=bridge_poll_interval_s,
        )
        if not ok:
            return f"{start_msg}\n\n{result}"
        try:
            retry = _request_http(
                action,
                only_small_group_calls=only_small_group_calls,
                min_humans_in_channel=min_humans_in_channel,
                max_humans_in_channel=max_humans_in_channel,
                ping_friend_user_ids=ping_friend_user_ids,
                open_discord_desktop_if_none=open_discord_desktop_if_none,
                allow_join_other_sessions=allow_join_other_sessions,
                music_device=music_device,
                target_name=target_name,
                message=message,
                control_timeout_s=control_timeout_s,
            )
        except httpx.ConnectError:
            return f"{start_msg}\n\nBridge started but HTTP still unreachable — check logs/discord-voice.err.log."
        except httpx.HTTPError as exc:
            return f"{start_msg}\n\nDiscord voice control HTTP error after start: {exc}"
        if not _needs_bridge_start(retry):
            return retry
        return f"{start_msg}\n\n{retry}"

    return result

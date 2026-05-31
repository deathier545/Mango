"""Local HTTP control for the Discord voice bridge (used by the ``discord_voice`` desktop tool).

The bridge process holds the only valid Gateway session for the user token. Desktop Mango
calls ``127.0.0.1`` (optional header ``X-Mango-Discord-Control`` when ``MANGO_DISCORD_CONTROL_SECRET`` is set).

Endpoints: ``GET /v1/voice/status``, ``POST /v1/voice/sync`` (pick/join a session),
``POST /v1/voice/leave`` (disconnect), ``POST /v1/voice/speak``
(JSON ``{"text": "..."}``) to play TTS into the **already joined** voice session, and
``POST /v1/voice/music/start|stop`` to stream a local Windows audio capture device into Discord.
There is no capture of other participants for STT (that stays on the desktop mic path).

Since the bridge runs as a discord.py-self **selfbot** (a user account), it can see and
join not only server voice channels but also 1:1 DM calls and group-DM calls (which bot
accounts cannot do).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import discord
from discord.ext import commands

from mango.integrations.discord.discord_voice_client import (
    CONTROL_HEADER,
    notify_channel_id,
    owner_user_id,
    preferred_guild_id,
)
from mango.persona import owner_display_name_from_env

logger = logging.getLogger(__name__)

DEFAULT_MUSIC_DEVICE = "CABLE Output (VB-Audio Virtual Cable)"
_music_raw_source: discord.FFmpegPCMAudio | None = None
_music_transformer: discord.PCMVolumeTransformer | None = None
_music_device: str | None = None
_last_known_non_dylan: list[str] = []
_last_people_text: str = ""


def _known_people_map() -> dict[str, str]:
    """Discord username → roster display label (override with MANGO_DISCORD_KNOWN_PEOPLE_JSON)."""
    raw = os.getenv("MANGO_DISCORD_KNOWN_PEOPLE_JSON", "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and parsed:
                return {
                    str(k).strip(): str(v).strip()
                    for k, v in parsed.items()
                    if str(k).strip() and str(v).strip()
                }
        except json.JSONDecodeError:
            logger.warning("Invalid MANGO_DISCORD_KNOWN_PEOPLE_JSON; using built-in defaults.")
    self_u = (os.getenv("MANGO_DISCORD_SELFBOT_USERNAME", "onlydecisions") or "onlydecisions").strip()
    owner_label = owner_display_name_from_env()
    return {
        "lovee_ariana": "Ariana",
        ".brook.e": "Brooke",
        self_u: owner_label,
    }


def _greet_exclude_usernames() -> set[str]:
    """Lowercased Discord usernames never targeted by greet_everyone (owner alts, etc.)."""
    raw = os.getenv("MANGO_DISCORD_GREET_EXCLUDE_USERNAMES", "onlydecisions").strip()
    return {p.strip().casefold() for p in raw.split(",") if p.strip()}


@dataclass
class CallSession:
    """A joinable voice session — server VC, DM call, or group-DM call."""

    label: str
    channel: Any  # discord.VoiceChannel | discord.DMChannel | discord.GroupChannel
    humans: int
    kind: str  # "guild" | "dm" | "group"

    @property
    def sort_key(self) -> tuple[int, str]:
        return (self.humans, self.label.casefold())


def humans_in_voice(channel: discord.VoiceChannel) -> int:
    return sum(1 for m in channel.members if not m.bot)


def _group_label(ch: discord.GroupChannel) -> str:
    name = (getattr(ch, "name", None) or "").strip()
    if name:
        return f"Group call: {name}"
    parts = []
    for r in list(getattr(ch, "recipients", []) or [])[:3]:
        parts.append(getattr(r, "display_name", None) or getattr(r, "name", None) or str(r.id))
    if not parts:
        return "Group call"
    extra = max(0, len(ch.recipients) - 3)
    suffix = f" +{extra} more" if extra else ""
    return f"Group call: {', '.join(parts)}{suffix}"


def _dm_label(ch: discord.DMChannel) -> str:
    other = getattr(ch, "recipient", None)
    name = getattr(other, "display_name", None) or getattr(other, "name", None) if other else None
    return f"DM call with {name}" if name else "DM call"


def _user_label(user: Any) -> str:
    display = getattr(user, "display_name", None) or getattr(user, "global_name", None)
    username = getattr(user, "name", None)
    if display and username and display != username:
        return f"{display} (@{username})"
    if username:
        return f"@{username}"
    if display:
        return str(display)
    uid = getattr(user, "id", None)
    return str(uid) if uid is not None else "unknown"


def _username(user: Any) -> str:
    return str(getattr(user, "name", "") or "").strip()


def _display_name(user: Any) -> str:
    return str(
        getattr(user, "display_name", None)
        or getattr(user, "global_name", None)
        or getattr(user, "name", None)
        or ""
    ).strip()


def _session_users(bot: commands.Bot, session: CallSession) -> list[Any]:
    if session.kind == "guild":
        return [
            m
            for m in getattr(session.channel, "members", [])
            if not getattr(m, "bot", False)
        ]
    users: list[Any] = []
    if bot.user is not None:
        users.append(bot.user)
    if session.kind == "dm":
        recipient = getattr(session.channel, "recipient", None)
        if recipient is not None:
            users.append(recipient)
    elif session.kind == "group":
        users.extend(getattr(session.channel, "recipients", []) or [])
    return users


def _session_people(bot: commands.Bot, session: CallSession) -> list[str]:
    return [_user_label(u) for u in _session_users(bot, session)]


def _people_text(bot: commands.Bot, session: CallSession) -> str:
    people = _session_people(bot, session)
    return ", ".join(people) if people else "unknown"


def _remember_session(bot: commands.Bot, session: CallSession) -> None:
    global _last_known_non_dylan, _last_people_text
    _last_known_non_dylan = _greeting_targets(bot, session)
    _last_people_text = _people_text(bot, session)


def _current_session(bot: commands.Bot) -> CallSession | None:
    vcs = [v for v in bot.voice_clients if v.is_connected()]
    if not vcs:
        return None
    channel_id = getattr(getattr(vcs[0], "channel", None), "id", None)
    if channel_id is None:
        return None
    return next(
        (
            s
            for s in _enumerate_sessions(bot)
            if getattr(s.channel, "id", None) == channel_id
        ),
        None,
    )


def _human_join(items: list[str]) -> str:
    if not items:
        return "no one"
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _enumerate_sessions(bot: commands.Bot) -> list[CallSession]:
    """All joinable sessions: guild VCs with humans, plus active DM/group calls."""
    out: list[CallSession] = []

    pgid = preferred_guild_id()
    if pgid is None:
        guilds = list(bot.guilds)
    else:
        g = bot.get_guild(pgid)
        guilds = [g] if g else []

    for guild in guilds:
        for ch in guild.voice_channels:
            h = humans_in_voice(ch)
            if h > 0:
                out.append(
                    CallSession(
                        label=f"{guild.name} / #{ch.name}",
                        channel=ch,
                        humans=h,
                        kind="guild",
                    )
                )

    # Private (DM / group) calls are only relevant when no preferred guild is set
    # (the original scope semantics treated PREFERRED_GUILD_ID as a hard filter).
    if pgid is None:
        for pch in list(bot.private_channels):
            if isinstance(pch, discord.DMChannel):
                if getattr(pch, "call", None) is None:
                    continue
                out.append(
                    CallSession(
                        label=_dm_label(pch),
                        channel=pch,
                        humans=2,
                        kind="dm",
                    )
                )
            elif isinstance(pch, discord.GroupChannel):
                if getattr(pch, "call", None) is None:
                    continue
                # Upper-bound estimate: every recipient + ourselves. Discord doesn't
                # always tell selfbots exactly who is *currently* in the call without
                # subscribing, so size-based filtering uses this conservative count.
                humans = max(2, len(getattr(pch, "recipients", []) or []) + 1)
                out.append(
                    CallSession(
                        label=_group_label(pch),
                        channel=pch,
                        humans=humans,
                        kind="group",
                    )
                )

    return out


async def _member(guild: discord.Guild, user_id: int) -> discord.Member | None:
    m = guild.get_member(user_id)
    if m:
        return m
    try:
        return await guild.fetch_member(user_id)
    except (discord.NotFound, discord.HTTPException):
        return None


async def _owner_session(bot: commands.Bot, sessions: list[CallSession]) -> CallSession | None:
    """Find the session the configured owner is currently in (server VC), if any.

    On the selfbot path the "owner" defaults to our own ``bot.user.id`` if unset.
    DM/group sessions are inherently ones we participate in (we are the recipient),
    so they always count as "owner present".
    """
    oid = owner_user_id() or (bot.user.id if bot.user else None)
    if oid is None:
        return None
    for s in sessions:
        if s.kind == "guild":
            guild = s.channel.guild
            mem = await _member(guild, oid)
            if (
                mem
                and mem.voice
                and mem.voice.channel
                and mem.voice.channel.id == s.channel.id
            ):
                return s
        else:
            # DM/group: we are always a recipient, so this is implicitly "ours" if
            # the configured owner is the selfbot account itself.
            if bot.user and oid == bot.user.id:
                return s
    return None


async def _disconnect_all_voice(bot: commands.Bot) -> None:
    _stop_music_playback()
    for vc in list(bot.voice_clients):
        try:
            await vc.disconnect(force=True)
        except Exception:
            logger.exception("disconnect voice client")


async def _join_session(bot: commands.Bot, session: CallSession) -> None:
    target_id = getattr(session.channel, "id", None)
    if target_id is not None:
        for vc in list(bot.voice_clients):
            if not vc.is_connected():
                continue
            ch = getattr(vc, "channel", None)
            if ch is not None and getattr(ch, "id", None) == target_id:
                logger.info("Discord voice: already in %s — skip disconnect/rejoin", session.label)
                return
    await _disconnect_all_voice(bot)
    if session.kind in ("dm", "group"):
        await session.channel.connect()
    else:
        await session.channel.connect(self_deaf=False, self_mute=False)


async def voice_leave_payload(bot: commands.Bot) -> dict[str, Any]:
    """Disconnect from all Discord voice sessions and stop any active stream."""
    connected = [vc for vc in bot.voice_clients if vc.is_connected()]
    await _disconnect_all_voice(bot)
    if connected:
        return {"ok": True, "left": True, "lines": ["Left Discord voice and stopped any active audio stream."]}
    return {"ok": True, "left": False, "lines": ["Not connected to Discord voice."]}


def _music_is_playing() -> bool:
    return _music_transformer is not None


def _stop_music_playback() -> bool:
    global _music_device, _music_raw_source, _music_transformer
    src = _music_raw_source
    if src is None and _music_transformer is None:
        return False
    try:
        if src is not None:
            src.cleanup()
    except Exception:
        logger.debug("music source cleanup failed", exc_info=True)
    _music_raw_source = None
    _music_transformer = None
    _music_device = None
    return True


def set_discord_music_stream_volume(level: float) -> bool:
    """Adjust live CABLE→Discord stream gain (``PCMVolumeTransformer``)."""
    if _music_transformer is None:
        return False
    clamped = max(0.0, min(2.0, float(level)))
    _music_transformer.volume = clamped
    logger.info("Discord music stream volume -> %.3f", clamped)
    return True


def discord_music_stream_volume() -> float:
    if _music_transformer is None:
        return 1.0
    return float(_music_transformer.volume)


def _new_music_source(device: str) -> discord.FFmpegPCMAudio:
    return discord.FFmpegPCMAudio(
        f"audio={device}",
        before_options="-f dshow",
        options="-vn",
    )


def _start_music_playback(vc: discord.VoiceClient, device: str) -> None:
    global _music_device, _music_raw_source, _music_transformer
    raw = _new_music_source(device)
    transformer = discord.PCMVolumeTransformer(raw, volume=1.0)

    def _after(err: BaseException | None) -> None:
        if err:
            logger.warning("Discord music stream ended with err=%s", err)
        _stop_music_playback()

    _music_raw_source = raw
    _music_transformer = transformer
    _music_device = device
    try:
        vc.play(transformer, after=_after)
    except Exception:
        _stop_music_playback()
        raise


async def voice_music_duck_payload(bot: commands.Bot, body: dict[str, Any]) -> dict[str, Any]:
    """Lower the active CABLE capture stream sent into Discord voice."""
    del bot  # bridge state is global
    if not _music_is_playing():
        return {"ok": True, "lines": ["Discord music stream is not active."]}
    try:
        level = float(body.get("level", 0.12))
    except (TypeError, ValueError):
        level = 0.12
    level = max(0.0, min(1.0, level))
    if set_discord_music_stream_volume(level):
        return {
            "ok": True,
            "lines": [f"Lowered Discord music stream to {level * 100:.0f}% while Mango is speaking."],
        }
    return {"ok": False, "lines": ["Could not adjust Discord music stream volume."]}


async def voice_music_restore_payload(bot: commands.Bot, body: dict[str, Any]) -> dict[str, Any]:
    """Restore Discord music stream to full level."""
    del bot, body
    if not _music_is_playing():
        return {"ok": True, "lines": ["Discord music stream is not active."]}
    if set_discord_music_stream_volume(1.0):
        return {"ok": True, "lines": ["Restored Discord music stream volume."]}
    return {"ok": False, "lines": ["Could not restore Discord music stream volume."]}


async def voice_status_payload(bot: commands.Bot) -> dict[str, Any]:
    sessions = _enumerate_sessions(bot)
    sessions.sort(key=lambda s: s.sort_key)

    owner_session = await _owner_session(bot, sessions)
    if owner_session is not None:
        _remember_session(bot, owner_session)
    owner_loc = (
        f"{owner_session.label} ({owner_session.humans} human(s))" if owner_session else None
    )

    lines = [f"Active voice sessions (humans > 0 / active calls): {len(sessions)}"]
    if preferred_guild_id():
        lines.append(f"(scoped to preferred guild id {preferred_guild_id()} — DM/group calls hidden)")
    for s in sessions[:40]:
        kind_marker = {"guild": "", "dm": " [DM]", "group": " [group]"}.get(s.kind, "")
        lines.append(
            f"- {s.label}{kind_marker}: {s.humans} human(s) "
            f"(id {s.channel.id}); people: {_people_text(bot, s)}"
        )
    if len(sessions) > 40:
        lines.append(f"… and {len(sessions) - 40} more")
    oid = owner_user_id() or (bot.user.id if bot.user else None)
    if oid:
        lines.append(
            f"Configured owner user id {oid}: {owner_loc or 'not in any listed voice session'}"
        )
    if _music_is_playing():
        lines.append(f"Music stream: on ({_music_device or DEFAULT_MUSIC_DEVICE})")
    else:
        lines.append("Music stream: off")
    return {"ok": True, "sessions": len(sessions), "owner_voice": owner_loc, "lines": lines}


async def voice_sync_payload(bot: commands.Bot, body: dict[str, Any]) -> dict[str, Any]:
    messages: list[str] = []
    only_small = bool(body.get("only_small_group_calls", True))
    max_h = int(body.get("max_humans_in_channel", 4) or 4)
    max_h = max(2, min(99, max_h))
    min_h = int(body.get("min_humans_in_channel", 2) or 2)
    min_h = max(1, min(max_h, min_h))
    ping_ids_raw = body.get("ping_friend_user_ids") or []
    ping_ids: list[int] = []
    if isinstance(ping_ids_raw, list):
        for x in ping_ids_raw:
            try:
                ping_ids.append(int(str(x).strip()))
            except (TypeError, ValueError):
                continue
    open_discord = bool(body.get("open_discord_desktop_if_none", False))
    allow_other = bool(body.get("allow_join_other_sessions", False))

    def passes_filters(h: int) -> bool:
        if h < min_h:
            return False
        if only_small and h > max_h:
            return False
        return True

    sessions = _enumerate_sessions(bot)

    chosen: CallSession | None = None
    owner_session = await _owner_session(bot, sessions)
    if owner_session is not None:
        if passes_filters(owner_session.humans):
            chosen = owner_session
            messages.append(
                f"You are in {owner_session.label} ({owner_session.humans} human(s); "
                f"people: {_people_text(bot, owner_session)}) — joining that session."
            )
        else:
            messages.append(
                f"You are in {owner_session.label} with {owner_session.humans} human(s); filters want "
                f"min={min_h}, max={'no cap' if not only_small else max_h} — not auto-joining that channel."
            )

    if chosen is None and allow_other:
        candidates = [s for s in sessions if passes_filters(s.humans)]
        candidates.sort(key=lambda s: (abs(s.humans - 2), s.humans, s.label.casefold()))
        if candidates:
            chosen = candidates[0]
            messages.append(
                f"No filtered match for your own channel; joining smallest qualifying session "
                f"{chosen.label} ({chosen.humans} human(s); people: {_people_text(bot, chosen)})."
            )
    elif chosen is None:
        messages.append(
            "No matching owner/self session found. I will not join another call unless explicitly allowed."
        )

    if chosen is not None:
        try:
            _remember_session(bot, chosen)
            target_id = getattr(chosen.channel, "id", None)
            already_there = target_id is not None and any(
                vc.is_connected()
                and getattr(getattr(vc, "channel", None), "id", None) == target_id
                for vc in bot.voice_clients
            )
            if already_there:
                messages.append(
                    f"Already connected to {chosen.label}. "
                    f"People in call: {_people_text(bot, chosen)}."
                )
            else:
                await _join_session(bot, chosen)
                messages.append(
                    f"Now connected to voice: {chosen.label}. People in call: {_people_text(bot, chosen)}."
                )
            return {
                "ok": True,
                "joined": True,
                "channel_id": chosen.channel.id,
                "kind": chosen.kind,
                "lines": messages,
            }
        except Exception as exc:
            logger.exception("Join voice failed")
            return {
                "ok": False,
                "joined": False,
                "error": str(exc),
                "lines": messages + [f"Join failed: {exc}"],
            }

    messages.append(
        "No qualifying voice session found (checked server voice channels, DM calls, and "
        "group calls within the configured scope)."
    )

    nid = notify_channel_id()
    if nid and ping_ids:
        ch_notify = bot.get_channel(nid)
        if isinstance(ch_notify, discord.TextChannel):
            mentions = " ".join(f"<@{uid}>" for uid in ping_ids)
            try:
                await ch_notify.send(
                    f"{mentions} Mango could not find a small voice session to join. "
                    f"Start or join a voice channel (≤{max_h} people) and run sync again.",
                )
                messages.append(f"Posted a ping in #{ch_notify.name}.")
            except Exception as exc:
                logger.exception("Notify channel send failed")
                messages.append(f"Could not post to notify channel: {exc}")
        else:
            messages.append(
                f"MANGO_DISCORD_NOTIFY_CHANNEL_ID={nid} is not a text channel this account can use."
            )
    elif ping_ids and not nid:
        messages.append(
            "Friend user ids were provided but MANGO_DISCORD_NOTIFY_CHANNEL_ID is not set — no ping sent."
        )

    if open_discord:
        try:
            from mango.tools import open_app

            messages.append(open_app.run("discord"))
        except Exception as exc:
            logger.exception("open_app discord failed")
            messages.append(f"Could not open Discord desktop: {exc}")

    return {"ok": True, "joined": False, "lines": messages}


async def voice_speak_payload(bot: commands.Bot, body: dict[str, Any]) -> dict[str, Any]:
    """Play TTS into the current voice connection (no STT from the call)."""
    text = str(body.get("text") or "").strip()
    if not text:
        return {"ok": False, "lines": ["Missing or empty `text` in JSON body."]}
    if len(text) > 4000:
        text = text[:4000]

    vcs = [v for v in bot.voice_clients if v.is_connected()]
    if not vcs:
        return {
            "ok": False,
            "lines": [
                "Not connected to Discord voice. Run `discord_voice` sync, `!join`, or enable "
                "`MANGO_DISCORD_AUTO_SYNC_ON_READY=1` first.",
            ],
        }
    vc = vcs[0]
    resume_music_device = _music_device if _music_is_playing() else None
    if vc.is_playing():
        if _music_is_playing():
            vc.stop()
            _stop_music_playback()
            await asyncio.sleep(0.2)
        else:
            return {"ok": False, "lines": ["Already playing audio in voice — wait for it to finish."]}

    from mango.config import Config
    from mango.integrations.discord.discord_voice_audio import play_tts_in_voice

    cfg = Config.load()
    try:
        await play_tts_in_voice(vc, cfg, text)
    except Exception as exc:
        logger.exception("voice_speak")
        return {"ok": False, "lines": [f"TTS playback failed: {exc}"]}
    if resume_music_device:
        try:
            _start_music_playback(vc, resume_music_device)
        except Exception as exc:
            logger.exception("music resume failed")
            return {
                "ok": True,
                "lines": [
                    "Played TTS in Discord voice, but could not resume the music stream: "
                    f"{exc}",
                ],
            }
    return {
        "ok": True,
        "lines": [
            "Played TTS in Discord voice (output only; other call participants were not recorded)."
            + (" Music stream resumed." if resume_music_device else ""),
        ],
    }


async def voice_music_start_payload(bot: commands.Bot, body: dict[str, Any]) -> dict[str, Any]:
    """Stream a local Windows audio capture device into the current Discord voice session."""
    global _music_device, _music_source
    vcs = [v for v in bot.voice_clients if v.is_connected()]
    if not vcs:
        return {
            "ok": False,
            "lines": [
                "Not connected to Discord voice. Run `discord_voice` sync or `!join` first.",
            ],
        }
    vc = vcs[0]
    if vc.is_playing():
        if _music_is_playing():
            return {"ok": True, "lines": [f"Music stream is already on ({_music_device})."]}
        return {"ok": False, "lines": ["Already playing TTS/audio in voice — wait or stop it first."]}

    device = str(
        body.get("device")
        or os.getenv("MANGO_DISCORD_MUSIC_DEVICE")
        or DEFAULT_MUSIC_DEVICE
    ).strip()
    if not device:
        device = DEFAULT_MUSIC_DEVICE
    try:
        _start_music_playback(vc, device)
    except Exception as exc:
        logger.exception("music_start")
        return {"ok": False, "lines": [f"Could not start music stream: {exc}"]}
    return {
        "ok": True,
        "lines": [
            f"Streaming Windows audio device `{device}` into Discord voice. "
            "Set Spotify output to `CABLE Input` to feed this stream.",
        ],
    }


async def voice_music_stop_payload(bot: commands.Bot) -> dict[str, Any]:
    """Stop the active music stream, if any."""
    stopped = False
    for vc in bot.voice_clients:
        if vc.is_connected() and vc.is_playing() and _music_is_playing():
            vc.stop()
            stopped = True
            break
    stopped = _stop_music_playback() or stopped
    if stopped:
        return {"ok": True, "lines": ["Stopped Discord music stream."]}
    return {"ok": True, "lines": ["Discord music stream was not running."]}


def _known_name_for_user(user: Any, known: dict[str, str] | None = None) -> str | None:
    username = _username(user).casefold()
    display = _display_name(user).casefold()
    m = known if known is not None else _known_people_map()
    for known_username, name in m.items():
        key = known_username.casefold()
        if username == key or display == key:
            return name
    return None


def _greeting_targets(bot: commands.Bot, session: CallSession) -> list[str]:
    targets: list[str] = []
    bot_username = _username(bot.user).casefold() if bot.user is not None else ""
    exclude = {bot_username} | _greet_exclude_usernames()
    known = _known_people_map()
    for user in _session_users(bot, session):
        username = _username(user).casefold()
        if username in exclude:
            continue
        name = _known_name_for_user(user, known)
        if name and name not in targets:
            targets.append(name)
    return targets


def _resolve_known_target(raw: str) -> str | None:
    target = (raw or "").strip().casefold()
    if not target:
        return None
    if target in ("her", "him", "them", "that person"):
        return _last_known_non_dylan[0] if len(_last_known_non_dylan) == 1 else None
    pmap = _known_people_map()
    for name in pmap.values():
        if target == name.casefold():
            return name
    for username, name in pmap.items():
        if target == username.casefold() or target == f"@{username}".casefold():
            return name
    return None


async def voice_who_payload(bot: commands.Bot) -> dict[str, Any]:
    """Return a natural summary of the current Discord call roster."""
    current = _current_session(bot)
    if current is None:
        if _last_people_text:
            return {
                "ok": True,
                "connected": False,
                "lines": [
                    "Not connected to Discord voice right now.",
                    f"Last known call roster: {_last_people_text}",
                ],
            }
        return {"ok": True, "connected": False, "lines": ["Not connected to Discord voice right now."]}
    _remember_session(bot, current)
    known = _greeting_targets(bot, current)
    owner = owner_display_name_from_env()
    if known:
        summary = f"{_human_join(known)} {'is' if len(known) == 1 else 'are'} in call with {owner}."
    else:
        summary = f"No other recognized guests in the current call with {owner}."
    return {
        "ok": True,
        "connected": True,
        "known_people": known,
        "lines": [
            summary,
            f"Raw roster: {_people_text(bot, current)}",
        ],
    }


async def voice_greet_payload(bot: commands.Bot) -> dict[str, Any]:
    """Greet known people in the current call, excluding the selfbot account and configured alts."""
    vcs = [v for v in bot.voice_clients if v.is_connected()]
    if not vcs:
        return {
            "ok": False,
            "lines": ["Not connected to Discord voice. Run `discord_voice` sync first."],
        }
    current = _current_session(bot)
    if current is None:
        return {"ok": False, "lines": ["Connected to voice, but could not identify the call roster."]}
    _remember_session(bot, current)
    targets = _greeting_targets(bot, current)
    owner = owner_display_name_from_env()
    if not targets:
        return {
            "ok": True,
            "lines": [
                f"People in call: {_people_text(bot, current)}",
                f"No other recognized guests to greet besides {owner}.",
            ],
        }
    text = " ".join(f"Hello {name}." for name in targets)
    result = await voice_speak_payload(bot, {"text": text})
    lines = [
        f"People in call: {_people_text(bot, current)}",
        f"Greeting spoken: {text}",
    ]
    lines.extend(str(x) for x in result.get("lines", []))
    return {"ok": bool(result.get("ok", True)), "greeted": targets, "lines": lines}


async def voice_say_to_payload(bot: commands.Bot, body: dict[str, Any]) -> dict[str, Any]:
    """Speak a short message addressed to a known person currently in the call."""
    current = _current_session(bot)
    if current is None:
        return {"ok": False, "lines": ["Not connected to Discord voice. Run `discord_voice` sync first."]}
    _remember_session(bot, current)
    target = _resolve_known_target(str(body.get("target") or ""))
    if target is None:
        return {
            "ok": False,
            "lines": [
                "Could not resolve that person from the current/last call roster.",
                f"Recognized guests (other than {owner_display_name_from_env()}): {_human_join(_last_known_non_dylan)}",
            ],
        }
    present = _greeting_targets(bot, current)
    if target not in present:
        return {
            "ok": False,
            "lines": [
                f"{target} is not currently recognized in the call.",
                f"Recognized guests (other than {owner_display_name_from_env()}): {_human_join(present)}",
            ],
        }
    message = str(body.get("message") or "").strip()
    if not message:
        message = f"Hello {target}."
    elif target.casefold() not in message.casefold():
        message = f"{target}, {message}"
    result = await voice_speak_payload(bot, {"text": message})
    lines = [
        f"People in call: {_people_text(bot, current)}",
        f"Spoken to {target}: {message}",
    ]
    lines.extend(str(x) for x in result.get("lines", []))
    return {"ok": bool(result.get("ok", True)), "target": target, "lines": lines}


def create_control_handler_class(
    bot: commands.Bot,
    expected_secret: str,
) -> type[BaseHTTPRequestHandler]:
    """Factory: handler closes over ``bot``. If ``expected_secret`` is empty, requests are allowed (127.0.0.1 only)."""

    class DiscordVoiceControlHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: Any) -> None:
            logger.info("discord_voice_control %s - %s", self.address_string(), fmt % args)

        def _check_secret(self) -> bool:
            if not expected_secret:
                return True
            got = (self.headers.get(CONTROL_HEADER) or "").strip()
            return got == expected_secret

        def _send_cors_headers(self) -> None:
            # Mango Console (Vite/Electron) polls from another localhost origin.
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", f"Content-Type, {CONTROL_HEADER}")

        def _json_response(self, code: int, payload: dict[str, Any]) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(raw)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self._send_cors_headers()
            self.end_headers()

        def _run_coro(self, coro: Any, timeout: float = 90.0) -> Any:
            fut = asyncio.run_coroutine_threadsafe(coro, bot.loop)
            return fut.result(timeout=timeout)

        def do_GET(self) -> None:  # noqa: N802
            if self.path.split("?", 1)[0] != "/v1/voice/status":
                self.send_error(404)
                return
            if not self._check_secret():
                self.send_error(401)
                return
            try:
                payload = self._run_coro(voice_status_payload(bot))
                self._json_response(200, payload)
            except Exception as exc:
                logger.exception("status handler")
                self._json_response(500, {"ok": False, "error": str(exc)})

        def do_POST(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path not in (
                "/v1/voice/greet",
                "/v1/voice/leave",
                "/v1/voice/say-to",
                "/v1/voice/sync",
                "/v1/voice/speak",
                "/v1/voice/who",
                "/v1/voice/music/start",
                "/v1/voice/music/stop",
                "/v1/voice/music/duck",
                "/v1/voice/music/restore",
            ):
                self.send_error(404)
                return
            if not self._check_secret():
                self.send_error(401)
                return
            try:
                length = int(self.headers.get("Content-Length", "0") or "0")
                raw = self.rfile.read(min(length, 256_000)) if length > 0 else b"{}"
                try:
                    body = json.loads(raw.decode("utf-8") or "{}")
                except json.JSONDecodeError:
                    body = {}
                if not isinstance(body, dict):
                    body = {}
                if path == "/v1/voice/speak":
                    payload = self._run_coro(voice_speak_payload(bot, body))
                elif path == "/v1/voice/greet":
                    payload = self._run_coro(voice_greet_payload(bot))
                elif path == "/v1/voice/leave":
                    payload = self._run_coro(voice_leave_payload(bot))
                elif path == "/v1/voice/say-to":
                    payload = self._run_coro(voice_say_to_payload(bot, body))
                elif path == "/v1/voice/who":
                    payload = self._run_coro(voice_who_payload(bot))
                elif path == "/v1/voice/music/start":
                    payload = self._run_coro(voice_music_start_payload(bot, body))
                elif path == "/v1/voice/music/stop":
                    payload = self._run_coro(voice_music_stop_payload(bot))
                elif path == "/v1/voice/music/duck":
                    payload = self._run_coro(voice_music_duck_payload(bot, body))
                elif path == "/v1/voice/music/restore":
                    payload = self._run_coro(voice_music_restore_payload(bot, body))
                else:
                    payload = self._run_coro(voice_sync_payload(bot, body))
                self._json_response(200, payload)
            except Exception as exc:
                logger.exception("POST %s handler", path)
                self._json_response(500, {"ok": False, "error": str(exc)})

    return DiscordVoiceControlHandler


def start_control_server(
    bot: commands.Bot,
    secret: str,
    port: int,
) -> ThreadingHTTPServer:
    handler_cls = create_control_handler_class(bot, secret)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler_cls)
    httpd.daemon_threads = True
    return httpd

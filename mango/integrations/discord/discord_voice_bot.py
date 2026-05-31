"""Discord **selfbot** voice bridge: log in as your user account, join a VC (server, DM, or group call), and speak TTS into it.

Run separately from desktop Mango (no pygame mic)::

    python -m mango --discord-voice

**Audio model (what you asked for):**

- **Hearing you:** desktop Mango uses your **PC microphone** only (push-to-talk / always-listen). It does **not** pull other people’s audio from Discord for speech-to-text.
- **Speaking in Discord:** this bridge sends **TTS only** into the call (``!say``, or HTTP ``POST /v1/voice/speak``). There is **no** voice-receive / ``!listen`` path on discord.py-self — the bridge does **not** listen to the call for transcription.
- **Desktop ``MANGO_TTS_PLAYBACK=discord``:** main Mango can send LLM replies to this bridge only (no pygame reply audio) while still using the **headset mic** for STT on the desktop app.

Optional **startup scan:** set ``MANGO_DISCORD_AUTO_SYNC_ON_READY=1`` to run the same join logic as the ``discord_voice`` ``sync`` action a few seconds after login (server VCs + active DM/group calls within scope).

Requires:

- A Discord **user account token** (this library automates a user account, **not** a bot).
  Set ``MANGO_DISCORD_BOT_TOKEN`` or ``DISCORD_BOT_TOKEN`` in ``.env`` to that token.
- ``discord.py-self`` with the ``voice`` extra (``pip install 'discord.py-self[voice]'``) — see ``requirements.txt``.
- **FFmpeg** on PATH (used to decode MP3 for voice playback).
- Localhost HTTP API on ``127.0.0.1:MANGO_DISCORD_VOICE_CONTROL_PORT`` (default 37564) for the desktop
  ``discord_voice`` tool and ``/v1/voice/speak``. ``MANGO_DISCORD_CONTROL_SECRET`` is **optional**: if unset, no auth header is
  required (still bound to loopback only). If set, clients must send header ``X-Mango-Discord-Control``.

.. warning::

    Automating user accounts violates Discord's Terms of Service and can get the account
    terminated. Use a throwaway account you do not mind losing. discord.py-self also does
    **not** support voice receive, so there is no ``!listen`` command on the selfbot path.

This is an MVP: ``!join`` / ``!leave`` / ``!say …``. ``!join`` works in any server text
channel (joins the VC you are sitting in), in DMs (rings/joins the 1:1 call), and in group
DMs (joins the active group call).
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from typing import Any

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


def _discord_token() -> str:
    return (
        os.getenv("MANGO_DISCORD_BOT_TOKEN", "").strip()
        or os.getenv("DISCORD_BOT_TOKEN", "").strip()
    )


async def _resolve_join_target(ctx: commands.Context) -> Any:
    """Pick the channel to connect to for ``!join`` based on where the command was sent.

    - In a server text channel: the voice channel the author is currently sitting in.
    - In a DM: the DM channel itself (1:1 call with the other user).
    - In a group DM: the group channel (group call).
    """
    ch = ctx.channel
    if isinstance(ch, (discord.DMChannel, discord.GroupChannel)):
        return ch
    voice_state = getattr(ctx.author, "voice", None)
    if voice_state and voice_state.channel:
        return voice_state.channel
    return None


async def amain() -> None:
    from mango.config import Config
    from mango.integrations.discord.discord_voice_client import (
        CONTROL_HEADER,
        control_port,
        control_secret,
    )
    from mango.integrations.discord.discord_voice_control import start_control_server
    from mango.logging_setup import setup_logging

    setup_logging()
    token = _discord_token()
    if not token:
        raise SystemExit(
            "Missing MANGO_DISCORD_BOT_TOKEN (or DISCORD_BOT_TOKEN) in .env — add your Discord "
            "**user account** token (discord.py-self automates a real user; see "
            "https://discordpy-self.readthedocs.io/en/latest/authenticating.html)."
        )

    cfg = Config.load()

    # discord.py-self does not use the Intents system the way bot accounts do; users get
    # all gateway events by default. ``self_bot=True`` tells commands.Bot to only process
    # commands typed by *this* user (our own messages).
    bot = commands.Bot(command_prefix="!", self_bot=True, help_command=None)
    httpd_holder: list[Any] = [None]
    control_http_started = [False]

    @bot.event
    async def on_ready() -> None:
        logger.info(
            "Discord selfbot logged in as %s (%s)",
            bot.user,
            bot.user.id if bot.user else "?",
        )
        if control_http_started[0]:
            return
        control_http_started[0] = True
        sec = control_secret()
        port = control_port()
        try:
            httpd = start_control_server(bot, sec, port)
            httpd_holder[0] = httpd
            threading.Thread(
                target=httpd.serve_forever,
                daemon=True,
                name="mango-discord-voice-ctrl",
            ).start()
            if sec:
                logger.info(
                    "Voice control API http://127.0.0.1:%s/ (requires header %r; GET /v1/voice/status, "
                    "POST /v1/voice/sync, POST /v1/voice/speak)",
                    port,
                    CONTROL_HEADER,
                )
            else:
                logger.info(
                    "Voice control API http://127.0.0.1:%s/ (no auth — loopback only; set MANGO_DISCORD_CONTROL_SECRET to require %r). "
                    "GET /v1/voice/status, POST /v1/voice/sync, POST /v1/voice/speak",
                    port,
                    CONTROL_HEADER,
                )
        except OSError as exc:
            logger.warning("Could not bind voice control server on port %s: %s", port, exc)

        if os.getenv("MANGO_DISCORD_AUTO_SYNC_ON_READY", "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        ):

            async def _auto_sync_after_ready() -> None:
                await asyncio.sleep(4.0)
                from mango.integrations.discord.discord_voice_control import voice_sync_payload

                body: dict[str, Any] = {
                    "only_small_group_calls": os.getenv(
                        "MANGO_DISCORD_AUTO_SYNC_ONLY_SMALL", "1"
                    ).strip().lower()
                    not in ("0", "false", "no", "off"),
                    "min_humans_in_channel": 2,
                    "max_humans_in_channel": 4,
                    "open_discord_desktop_if_none": False,
                }
                try:
                    r = await voice_sync_payload(bot, body)
                    joined = r.get("joined")
                    lines = r.get("lines") or []
                    logger.info(
                        "MANGO_DISCORD_AUTO_SYNC_ON_READY finished joined=%s: %s",
                        joined,
                        " | ".join(str(x) for x in lines[:5]),
                    )
                except Exception:
                    logger.exception("MANGO_DISCORD_AUTO_SYNC_ON_READY failed")

            asyncio.create_task(_auto_sync_after_ready())

    @bot.command(name="join")
    async def join_cmd(ctx: commands.Context) -> None:
        target = await _resolve_join_target(ctx)
        if target is None:
            await ctx.reply(
                "Join a voice channel first (or run `!join` inside a DM / group chat to join its call)."
            )
            return
        existing = ctx.voice_client
        try:
            if existing is not None:
                await existing.move_to(target)
            elif isinstance(target, (discord.DMChannel, discord.GroupChannel)):
                await target.connect()
            else:
                await target.connect(self_deaf=False, self_mute=False)
        except discord.ClientException as exc:
            await ctx.reply(f"Already connected to a voice channel: {exc}")
            return
        label = getattr(target, "name", None) or "this call"
        await ctx.reply(f"Joined **{label}**. Try `!say Hello`.")

    @bot.command(name="leave")
    async def leave_cmd(ctx: commands.Context) -> None:
        if ctx.voice_client:
            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()
            await ctx.voice_client.disconnect(force=True)
            await ctx.reply("Left voice.")
        else:
            await ctx.reply("Not in a voice channel.")

    @bot.command(name="say")
    async def say_cmd(ctx: commands.Context, *, text: str) -> None:
        if not ctx.voice_client or not ctx.voice_client.is_connected():
            await ctx.reply("Use `!join` first (from a server text channel, DM, or group chat).")
            return
        vc = ctx.voice_client
        if vc.is_playing():
            await ctx.reply("Already playing — wait for it to finish.")
            return
        try:
            from mango.integrations.discord.discord_voice_audio import play_tts_in_voice

            await play_tts_in_voice(vc, cfg, text)
        except Exception as exc:
            logger.exception("TTS play failed")
            await ctx.reply(f"TTS failed: {exc}")
            return

        await ctx.reply("Done speaking in voice.")

    @bot.command(name="musicstart")
    async def music_start_cmd(ctx: commands.Context) -> None:
        from mango.integrations.discord.discord_voice_control import voice_music_start_payload

        result = await voice_music_start_payload(bot, {})
        await ctx.reply("\n".join(str(x) for x in result.get("lines", [])) or str(result))

    @bot.command(name="musicresume")
    async def music_resume_cmd(ctx: commands.Context) -> None:
        from mango.integrations.discord.discord_voice_control import voice_music_start_payload

        result = await voice_music_start_payload(bot, {})
        await ctx.reply("\n".join(str(x) for x in result.get("lines", [])) or str(result))

    @bot.command(name="musicstop")
    async def music_stop_cmd(ctx: commands.Context) -> None:
        from mango.integrations.discord.discord_voice_control import voice_music_stop_payload

        result = await voice_music_stop_payload(bot)
        await ctx.reply("\n".join(str(x) for x in result.get("lines", [])) or str(result))

    @bot.command(name="musicpause")
    async def music_pause_cmd(ctx: commands.Context) -> None:
        from mango.integrations.discord.discord_voice_control import voice_music_stop_payload

        result = await voice_music_stop_payload(bot)
        await ctx.reply("\n".join(str(x) for x in result.get("lines", [])) or str(result))

    @bot.command(name="who")
    async def who_cmd(ctx: commands.Context) -> None:
        from mango.integrations.discord.discord_voice_control import voice_who_payload

        result = await voice_who_payload(bot)
        await ctx.reply("\n".join(str(x) for x in result.get("lines", [])) or str(result))

    @bot.command(name="greet")
    async def greet_cmd(ctx: commands.Context) -> None:
        from mango.integrations.discord.discord_voice_control import voice_greet_payload

        result = await voice_greet_payload(bot)
        await ctx.reply("\n".join(str(x) for x in result.get("lines", [])) or str(result))

    @bot.command(name="mangohelp")
    async def help_cmd(ctx: commands.Context) -> None:
        await ctx.reply(
            "`!join` — join the VC you are sitting in (or the DM / group call you typed this in)\n"
            "`!leave` — disconnect\n"
            "`!say …` — speak text in voice (TTS into Discord only; your mic is desktop Mango)\n"
            "`!who` / `!greet` — summarize or greet known people in the current call\n"
            "`!musicstart` / `!musicpause` / `!musicresume` / `!musicstop` — control CABLE Output into Discord voice\n"
            "Desktop: `discord_voice` tool + `POST /v1/voice/speak` on localhost. Optional `MANGO_DISCORD_AUTO_SYNC_ON_READY=1`.\n"
            "Running on discord.py-self (user account); no voice receive / no listening to the call for STT."
        )

    try:
        await bot.start(token)
    finally:
        h = httpd_holder[0]
        if h is not None:
            try:
                h.shutdown()
            except Exception:
                logger.exception("voice control server shutdown")
        await bot.close()


if __name__ == "__main__":
    asyncio.run(amain())

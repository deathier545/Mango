"""Spoken progress: strict talk → action → talk → next action (fully blocking)."""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator
from urllib.parse import parse_qs, unquote_plus, urlparse

logger = logging.getLogger(__name__)

_narration_suppress_depth: ContextVar[int] = ContextVar("narration_suppress_depth", default=0)
_narration_interrupt_check: ContextVar[Any] = ContextVar("narration_interrupt_check", default=None)
_hud_level_sink: ContextVar[Any] = ContextVar("hud_level_sink", default=None)
_NARRATION_LOCK = threading.Lock()


def set_narration_hud_level(level_sink: Any | None) -> None:
    """Voice/desktop process: pass HUD level multiprocessing.Value for orb lip-sync."""
    _hud_level_sink.set(level_sink)


def set_narration_interrupt_check(interrupt_check: Any | None) -> None:
    """During a voice turn, wire PTT barge-in into tool narration TTS."""
    _narration_interrupt_check.set(interrupt_check)

_SKIP_TOOLS = frozenset({"globe_state", "globe_view"})
# Tool actions that speak inside the bridge — no pre-announce (action is the talk).
_SKIP_BEFORE: frozenset[tuple[str, str]] = frozenset(
    {
        ("web_search", ""),
        ("spotify_play", ""),
        ("phone_call", ""),
        ("run_powershell", ""),
        ("open_app", ""),
        ("close_app", ""),
        ("volume_control", "set"),
        ("volume_control", "mute"),
        ("volume_control", "unmute"),
    }
)


def narration_enabled() -> bool:
    return os.getenv("MANGO_TOOL_NARRATION", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def narration_after_enabled() -> bool:
    return os.getenv("MANGO_TOOL_NARRATION_AFTER", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


@contextmanager
def suppress_tool_narration() -> Iterator[None]:
    token = _narration_suppress_depth.set(_narration_suppress_depth.get() + 1)
    try:
        yield
    finally:
        _narration_suppress_depth.reset(token)


def _act(args: dict[str, Any]) -> str:
    return str(args.get("action") or "").strip().lower()


def _clip(text: str, n: int = 72) -> str:
    t = " ".join((text or "").split())
    if len(t) <= n:
        return t
    return t[: n - 1].rstrip() + "…"


def _spoken_web_target(value: str, max_query_len: int = 40) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if not re.match(r"^https?://", raw, flags=re.IGNORECASE):
        return _clip(raw, 48)
    try:
        parsed = urlparse(raw)
    except Exception:
        return "that page"
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if "youtube.com" in host:
        q = parse_qs(parsed.query).get("search_query", [""])[0].strip()
        if q:
            query = _clip(unquote_plus(q), max_query_len)
            return f"YouTube search results for {query}"
        if parsed.path.startswith("/watch"):
            return "a YouTube video"
        return "YouTube"
    if not host:
        return "that page"
    return host


def _spoken_youtube_query(value: str, max_query_len: int = 40) -> str:
    raw = (value or "").strip()
    if not raw or not re.match(r"^https?://", raw, flags=re.IGNORECASE):
        return ""
    try:
        parsed = urlparse(raw)
    except Exception:
        return ""
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if "youtube.com" not in host:
        return ""
    q = parse_qs(parsed.query).get("search_query", [""])[0].strip()
    if not q:
        return ""
    query = _clip(unquote_plus(q), max_query_len)
    if "video" not in query.casefold():
        query = f"{query} video"
    return query


def _neutralize_honorifics(line: str, honorific: str) -> str:
    text = (line or "").strip()
    if honorific in ("sir", "maam"):
        return text
    text = re.sub(r"\b(yes|of course|right away|understood)\s+sir,?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bsir\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s{2,}", " ", text).strip(" ,")
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return text or line


def _pick(seed: str, *lines: str) -> str:
    """Choose one phrasing variant (stable per tool step)."""
    if not lines:
        return "On it."
    return lines[sum(ord(c) for c in seed) % len(lines)]


def _result_ok(result: str) -> bool:
    t = (result or "").casefold()
    if not t:
        return False
    if t.startswith("err") or "error:" in t or "failed" in t[:40]:
        return False
    if "skipped" in t or "blocked" in t:
        return False
    return True


def tool_start_line(name: str, arguments: dict[str, Any]) -> str | None:
    """Line spoken immediately before a tool runs (Jarvis-style aide)."""
    args = arguments if isinstance(arguments, dict) else {}
    act = _act(args)
    key = (name, act)
    seed = f"{name}:{act}"

    if name in _SKIP_TOOLS:
        return None
    if key in _SKIP_BEFORE:
        return None
    if name == "run_routine":
        if act == "list":
            return _pick(
                seed,
                "Pulling up your routines.",
                "Checking your routines.",
            )
        if act == "run":
            return None
        return None

    if name == "discord_voice":
        if act == "ensure_bridge":
            return _pick(
                seed,
                "Starting the Discord bridge.",
                "Bringing the voice bridge online.",
            )
        if act == "sync":
            return _pick(
                seed,
                "Joining the Discord call now.",
                "Connecting to voice.",
                "Joining the channel.",
            )
        if act == "leave":
            return _pick(seed, "Leaving the call.", "Disconnecting from voice.")
        if act == "greet_everyone":
            return _pick(
                seed,
                "Greeting everyone in the call.",
                "Saying hello to the room.",
            )
        if act == "who_in_call":
            return _pick(seed, "Checking who's in the call.", "Looking at the roster.")
        if act == "status":
            return _pick(seed, "Checking Discord voice status.", "Voice status coming up.")
        if act in ("music_start", "music_resume"):
            return _pick(
                seed,
                "Streaming music into the call.",
                "Sending audio to the channel.",
            )
        if act in ("music_stop", "music_pause"):
            return _pick(seed, "Stopping the music.", "Music off.")
        if act == "say_to_person":
            who = _clip(str(args.get("target") or "them"), 32)
            return _pick(
                seed,
                f"Speaking to {who}.",
                f"A word for {who}.",
            )
        return _pick(seed, "Handling Discord voice.", "On Discord voice.")

    if name == "spotify_play":
        q = _clip(str(args.get("query") or ""), 56)
        if q:
            return _pick(
                seed,
                f"Queuing {q} on Spotify.",
                f"Putting on {q}.",
                f"Starting {q}.",
            )
        return _pick(seed, "Starting Spotify playback.", "Queuing on Spotify.")

    if name == "spotify_transport":
        mapping = {
            "play": _pick(seed, "Resuming Spotify.", "Play on."),
            "pause": _pick(seed, "Pausing Spotify.", "Holding the music."),
            "next": _pick(seed, "Next track.", "Skipping ahead."),
            "previous": _pick(seed, "Previous track.", "Going back one."),
        }
        return mapping.get(act, _pick(seed, "Adjusting Spotify.", "Spotify control."))

    if name == "spotify_session":
        return _pick(seed, "Checking Spotify.", "Spotify session.")

    if name == "volume_control":
        if act == "set":
            try:
                n = int(args.get("percent"))
                return _pick(
                    seed,
                    f"Setting volume to {n} percent.",
                    f"Volume to {n}.",
                )
            except (TypeError, ValueError):
                return _pick(seed, "Adjusting volume.", "Volume control.")
        if act == "mute":
            return _pick(seed, "Muting speakers.", "Audio muted.")
        if act == "unmute":
            return _pick(seed, "Unmuting.", "Sound back on.")
        if act == "toggle_mute":
            return _pick(seed, "Toggling mute.", "Mute toggle.")
        if act == "status":
            return _pick(seed, "Checking volume.", "Volume level.")
        return _pick(seed, "Adjusting volume.", "Audio levels.")

    if name == "open_app":
        app = _clip(str(args.get("app_name") or args.get("app") or args.get("name") or "that"), 40)
        raw_url = str(args.get("url") or "")
        yt_query = _spoken_youtube_query(raw_url)
        if yt_query:
            return f"Opening {yt_query} on YouTube now."
        page = _spoken_web_target(raw_url)
        if page:
            return _pick(
                seed,
                f"Opening {page} in {app}.",
                f"Loading {page} on {app}.",
            )
        return _pick(
            seed,
            f"Opening {app} now.",
            f"Bringing up {app}.",
        )
    if name == "close_app":
        app = _clip(str(args.get("app") or args.get("name") or "that"), 40)
        return _pick(
            seed,
            f"Closing {app}.",
            f"Shutting down {app}.",
        )

    if name == "web_search":
        q = _clip(str(args.get("query") or ""), 56)
        if q:
            return _pick(
                seed,
                f"Searching for {q}.",
                f"Looking up {q}.",
            )
        return _pick(seed, "Searching the web.", "Web search.")

    if name == "search_files":
        q = _clip(str(args.get("query") or ""), 48)
        if q:
            return _pick(
                seed,
                f"Searching your files for {q}.",
                f"Hunting down {q}.",
            )
        return _pick(seed, "Searching your files.", "File search.")

    if name == "run_powershell":
        return _pick(seed, "Running that command.", "PowerShell on it.")

    if name == "phone_call":
        who = _clip(str(args.get("contact") or "them"), 32)
        return _pick(
            seed,
            f"Calling {who} now.",
            f"Placing the call to {who}.",
        )

    if name == "saved_contact_phone":
        who = _clip(str(args.get("contact") or "them"), 32)
        return _pick(
            seed,
            f"Finding {who}'s number.",
            f"Looking up {who}'s contact.",
        )

    if name == "xbox_console":
        mapping = {
            "turn_on": _pick(seed, "Waking the Xbox.", "Xbox power on."),
            "turn_off": _pick(seed, "Shutting down the Xbox.", "Xbox off."),
            "status": _pick(seed, "Checking the Xbox.", "Xbox status."),
            "list_games": _pick(seed, "Listing your games.", "Game library."),
            "launch": _pick(seed, "Launching that game.", "Starting the title."),
        }
        return mapping.get(act, _pick(seed, "On the Xbox.", "Xbox control."))

    if name == "desktop_notify":
        return _pick(seed, "Sending the notification.", "Desktop alert.")
    if name == "screenshot_desktop":
        return _pick(seed, "Capturing the screen.", "Screenshot.")
    if name == "read_clipboard":
        return _pick(seed, "Reading your clipboard.", "Clipboard contents.")
    if name == "clipboard_write":
        return _pick(seed, "Updating the clipboard.", "Clipboard write.")
    if name == "clipboard_ai":
        return _pick(seed, "Working on the clipboard.", "Clipboard assist.")
    if name == "reminders":
        return _pick(seed, "Checking reminders.", "Reminder update.")
    if name == "delay_timer":
        return _pick(seed, "Starting the timer.", "Timer on.")
    if name == "memory_card":
        return _pick(seed, "Updating memory.", "Memory cards.")
    if name == "daily_brief":
        return _pick(seed, "Your daily brief.", "Brief incoming.")
    if name == "badge_status":
        return _pick(seed, "Checking my badge progress.", "Pulling up my badges.")
    if name == "system_info":
        return _pick(seed, "Checking the system.", "System readout.")
    if name == "therapy_support":
        return _pick(seed, "Let's think that through.", "I'm with you on this.")
    if name == "product_research":
        prod = _clip(str(args.get("product") or "that"), 40)
        return _pick(
            seed,
            f"Researching {prod}.",
            f"Digging into {prod}.",
        )

    label = name.replace("_", " ")
    return _pick(seed, f"Working on {label}.", f"On it, {label}.")


def tool_done_line(name: str, arguments: dict[str, Any], result: str) -> str | None:
    """Short line spoken after a tool finishes, before the next tool starts."""
    if not _result_ok(result):
        return None
    args = arguments if isinstance(arguments, dict) else {}
    act = _act(args)
    t = (result or "").casefold()

    seed = f"{name}:{act}:done"
    if name == "discord_voice":
        if act == "ensure_bridge":
            return _pick(seed, "Bridge is up, sir.", "Discord bridge is ready, sir.")
        if act == "sync":
            if "joined" in t or "connected" in t or "already connected" in t:
                return _pick(
                    seed,
                    "We're in the channel, sir.",
                    "Connected to voice, sir.",
                    "In the call now, sir.",
                )
            return None
        if act == "greet_everyone":
            if "greeting spoken" in t or "hello" in t:
                return _pick(seed, "Everyone's been greeted, sir.", "Hellos delivered, sir.")
            return None
        if act in ("music_start", "music_resume"):
            if "music" in t or "stream" in t:
                return _pick(seed, "Music's in the call, sir.", "Streaming to voice now, sir.")
            return None
        if act == "leave":
            return _pick(seed, "Left the call, sir.", "Disconnected, sir.")
        return None

    if name == "volume_control" and act == "set":
        return _pick(seed, "Volume's set, sir.", "Audio level adjusted, sir.")

    if name == "spotify_play":
        if "track_played:" in t or "playing on spotify" in t:
            hint = extract_track_hint(result)
            if hint:
                return _pick(
                    seed,
                    f"Spotify's on with {hint}, sir.",
                    f"Playing {hint} now, sir.",
                )
            return _pick(seed, "Spotify's playing, sir.", "Track is on, sir.")
        return None

    if name == "web_search":
        return _pick(seed, "Search is back, sir.", "I've got results, sir.")

    if name == "open_app":
        app = _clip(str(args.get("app_name") or args.get("app") or args.get("name") or "it"), 40)
        page = _spoken_web_target(str(args.get("url") or ""))
        if page:
            return _pick(
                seed,
                f"{app} has {page} open, sir.",
                f"There you are sir, {page} in {app}.",
            )
        return _pick(
            seed,
            f"{app} should be up, sir.",
            f"There you are sir, {app}.",
            f"{app} is open, sir.",
        )

    if name == "close_app":
        app = _clip(str(args.get("app") or args.get("name") or "it"), 40)
        return _pick(seed, f"{app}'s closed, sir.", f"Shut down {app}, sir.")

    if name == "phone_call":
        return _pick(seed, "Call step done, sir.", "That's handled, sir.")

    if name == "search_files":
        return _pick(seed, "File search done, sir.", "Found what I could, sir.")

    return None


def routine_intro_line(routine_id: str) -> str | None:
    rid = (routine_id or "").replace("_", " ").strip()
    seed = f"routine:{rid or 'generic'}"
    if not rid:
        return _pick(seed, "Running that now.", "Routine starting.")
    return _pick(
        seed,
        f"Running the {rid} routine.",
        f"{rid} sequence coming up.",
        f"Starting {rid}.",
    )


def _prefer_discord_for_tool(name: str, arguments: dict[str, Any]) -> bool:
    """Step narration plays on the PC headset so the orb lip-sync works."""
    del name, arguments
    return False


def _drain_playback() -> None:
    try:
        from mango.audio import wait_playback_idle

        wait_playback_idle()
    except Exception as exc:
        logger.debug("wait_playback_idle: %s", exc)
    time.sleep(0.03)


def speak_progress(
    text: str,
    *,
    prefer_discord: bool = False,
    on_playback_start: Any | None = None,
    hud_level_out: Any | None = None,
    interrupt_check: Any | None = None,
) -> bool:
    """Speak and block until playback finishes. Returns True if interrupted."""
    line = (text or "").strip()
    if not line:
        return False
    check = interrupt_check if interrupt_check is not None else _narration_interrupt_check.get()
    level_out = hud_level_out if hud_level_out is not None else _hud_level_sink.get()
    with _NARRATION_LOCK:
        if prefer_discord:
            try:
                from mango.integrations.discord.discord_tts_client import speak_via_discord

                ok, detail = speak_via_discord(
                    line,
                    interrupt_check=check,
                    on_playback_start=on_playback_start,
                )
                if ok:
                    if "(interrupt)" in (detail or "").casefold():
                        logger.info("Tool narration interrupted (Discord): %s", line[:80])
                        return True
                    logger.info("Tool narration (Discord): %s", line[:80])
                    _drain_playback()
                    return False
                logger.info("Tool narration Discord unavailable (%s) — local.", detail)
            except Exception as exc:
                logger.warning("Tool narration Discord failed: %s", exc)

        try:
            from mango.audio import init_voice_mixer
            from mango.config import Config
            from mango.tts import make_tts

            cfg = Config.load()
            init_voice_mixer()
            line_out = _neutralize_honorifics(line, cfg.honorific)
            interrupted = make_tts(cfg).speak(
                line_out,
                interrupt_check=check,
                streaming=cfg.streaming_tts and len(line_out) > 120,
                hud_level_out=level_out,
                on_playback_start=on_playback_start,
            )
            logger.info("Tool narration (local): %s", line_out[:80])
            _drain_playback()
            return interrupted
        except Exception as exc:
            logger.warning("Tool narration local TTS failed: %s", exc)
    return False


def narrate_tool_before(name: str, arguments: dict[str, Any]) -> bool:
    """Speak before-tool line. Returns True if user barged in."""
    if not narration_enabled() or _narration_suppress_depth.get() > 0:
        return False
    line = tool_start_line(name, arguments)
    if not line:
        return False
    return speak_progress(line, prefer_discord=_prefer_discord_for_tool(name, arguments))


def narrate_tool_after(name: str, arguments: dict[str, Any], result: str) -> None:
    if not narration_enabled() or not narration_after_enabled():
        return
    if _narration_suppress_depth.get() > 0:
        return
    line = tool_done_line(name, arguments, result)
    if not line:
        return
    speak_progress(line, prefer_discord=_prefer_discord_for_tool(name, arguments))


def narrate_routine_step_after(
    tool: str,
    arguments: dict[str, Any],
    result: str,
) -> None:
    """After a routine step completes, speak before the next step starts."""
    if not narration_enabled() or not narration_after_enabled():
        return
    after = tool_done_line(tool, arguments, result)
    if not after:
        return
    speak_progress(after, prefer_discord=_prefer_discord_for_tool(tool, arguments))


def prefer_discord_for_tool(name: str, arguments: dict[str, Any]) -> bool:
    return _prefer_discord_for_tool(name, arguments)


def narrate_tool_start(name: str, arguments: dict[str, Any]) -> None:
    """Registry hook: before-tool line only (after line is separate)."""
    narrate_tool_before(name, arguments)


def short_completion_reply(routine_id: str, variables: dict[str, str], result: str) -> str:
    del result
    song = (variables.get("query") or "").strip()
    seed = f"done:{routine_id}"
    if song:
        return _pick(
            seed,
            f"All set. Discord is live with {song}.",
            f"All set. Playing {song} in Discord.",
        )
    return _pick(
        seed,
        "All set. Discord voice and music are running.",
        "All set. You're in voice with music on.",
    )


def extract_track_hint(result: str) -> str | None:
    for ln in (result or "").splitlines():
        if "track_played:" in ln.casefold() or "playing on spotify" in ln.casefold():
            m = re.search(r"track_played:\s*(.+)", ln, re.I)
            if m:
                return m.group(1).strip()[:80]
    return None

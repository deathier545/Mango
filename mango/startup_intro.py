"""Spoken greeting at launch: local time + optional weather via Open-Meteo (no API key)."""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

_DEFAULT_TZ = "America/Chicago"
_DEFAULT_PLACE = "DeKalb"
_DEFAULT_LAT = 41.9295
_DEFAULT_LON = -88.7504

_OPEN_METEO = "https://api.open-meteo.com/v1/forecast"


def _intro_enabled() -> bool:
    raw = os.getenv("MANGO_STARTUP_INTRO", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _wmo_phrase(code: int) -> str:
    """Short spoken summary from WMO weather code (Open-Meteo)."""
    if code == 0:
        return "clear skies"
    if code == 1:
        return "mostly clear weather"
    if code == 2:
        return "partly cloudy skies"
    if code == 3:
        return "overcast skies"
    if code in (45, 48):
        return "foggy conditions"
    if code in (51, 53, 55, 56, 57):
        return "drizzle"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "thunderstorms nearby"
    return "mixed conditions"


def fetch_weather_line(
    *,
    lat: float,
    lon: float,
    tz_name: str,
    place: str,
    timeout_s: float = 3.0,
) -> str:
    """Return one sentence about current conditions, or empty if unavailable."""
    base_params = {
        "latitude": str(lat),
        "longitude": str(lon),
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
    }
    attempts = [
        {**base_params, "timezone": tz_name},
        {**base_params, "timezone": "auto"},
        base_params,
    ]
    payload: dict[str, Any] | None = None
    last_err: str | None = None
    for params in attempts:
        url = f"{_OPEN_METEO}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "MangoVoiceAssistant/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            last_err = str(exc)
            time.sleep(0.2)
            continue
    if payload is None:
        logger.warning("Startup weather fetch failed for %s: %s", place, last_err or "unknown error")
        return ""

    current = payload.get("current") if isinstance(payload, dict) else None
    if not isinstance(current, dict):
        return ""

    try:
        temp = round(float(current["temperature_2m"]))
    except (KeyError, TypeError, ValueError):
        return ""

    code_raw = current.get("weather_code", 0)
    try:
        code = int(code_raw)
    except (TypeError, ValueError):
        code = 0
    phrase = _wmo_phrase(code)

    wind_raw = current.get("wind_speed_10m")
    wind_bit = ""
    try:
        w = float(wind_raw)
        if w >= 15:
            wind_bit = f", with winds around {round(w)} miles per hour"
    except (TypeError, ValueError):
        pass

    return f"In {place}, it's about {temp} degrees Fahrenheit with {phrase}{wind_bit}."


def build_startup_intro_text() -> str:
    """Full greeting string for TTS (time + optional weather).

    Weather defaults to DeKalb, IL when intro location env vars are unset.
    Set ``MANGO_INTRO_PLACE_NAME``, ``MANGO_INTRO_LAT``, and ``MANGO_INTRO_LON``
    to override that default.
    """
    tz_name = os.getenv("MANGO_INTRO_TIMEZONE", _DEFAULT_TZ).strip() or _DEFAULT_TZ
    place_raw = os.getenv("MANGO_INTRO_PLACE_NAME", "").strip() or _DEFAULT_PLACE
    lat_raw = os.getenv("MANGO_INTRO_LAT", "").strip()
    lon_raw = os.getenv("MANGO_INTRO_LON", "").strip()
    lat = _DEFAULT_LAT
    lon = _DEFAULT_LON
    if lat_raw:
        try:
            lat = float(lat_raw)
        except ValueError:
            logger.warning("Invalid MANGO_INTRO_LAT=%r — using default %.4f", lat_raw, _DEFAULT_LAT)
    if lon_raw:
        try:
            lon = float(lon_raw)
        except ValueError:
            logger.warning("Invalid MANGO_INTRO_LON=%r — using default %.4f", lon_raw, _DEFAULT_LON)
    weather_enabled = os.getenv("MANGO_STARTUP_WEATHER", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    weather = ""
    if weather_enabled:
        weather = fetch_weather_line(lat=lat, lon=lon, tz_name=tz_name, place=place_raw)

    try:
        tz = ZoneInfo(tz_name)
        now = datetime.now(tz)
    except Exception:
        try:
            tz = ZoneInfo(_DEFAULT_TZ)
            now = datetime.now(tz)
        except Exception:
            now = datetime.now().astimezone()
            logger.warning(
                "ZoneInfo unavailable for %r (install tzdata). Using PC local clock for intro time.",
                tz_name,
            )
    h12 = now.hour % 12 or 12
    minute = f"{now.minute:02d}"
    ampm = "A.M." if now.hour < 12 else "P.M."
    time_part = f"{h12}:{minute} {ampm}"
    weekday = now.strftime("%A")
    month_day = f"{now.strftime('%B')} {now.day}"

    if weather:
        tail = f"{weather} How may I help you?"
    elif weather_enabled:
        tail = f"I couldn't pull live weather in {place_raw} just now. How may I help you?"
    else:
        tail = "How may I help you?"

    return (
        f"Hello sir. Mango here. It's {time_part} on {weekday}, {month_day}. "
        f"{tail}"
    )


def maybe_play_startup_intro(
    tts: object,
    hud: object | None = None,
    *,
    skip: bool = False,
    cfg: Any = None,
    set_state: Any = None,
) -> None:
    """If enabled, speak the launch greeting before push-to-talk."""
    if skip:
        logger.debug("Startup intro skipped (quiet hours or host request).")
        return
    if not _intro_enabled():
        logger.debug("Startup intro skipped (MANGO_STARTUP_INTRO off).")
        return
    _set_hud = getattr(hud, "set_state", None) if hud is not None else None

    def _state(value: str) -> None:
        if callable(set_state):
            set_state(value)
        elif callable(_set_hud):
            _set_hud(value)

    try:
        _state("thinking")
        logger.info("MANGO_STATE: thinking")
        text = build_startup_intro_text()
        logger.info("Startup intro: %s", text[:160] + ("…" if len(text) > 160 else ""))

        def _intro_playback_start() -> None:
            _state("speaking")
            logger.info("MANGO_STATE: speaking")

        if cfg is not None and getattr(cfg, "tts_playback", "headset") == "discord":
            try:
                from mango.integrations.discord.discord_tts_client import speak_via_discord

                ok, msg = speak_via_discord(
                    text,
                    interrupt_check=None,
                    on_playback_start=_intro_playback_start,
                )
            except Exception as exc:
                ok, msg = False, str(exc)
            if ok:
                logger.info("Startup intro via Discord: %s", msg)
            else:
                logger.warning("Startup intro Discord failed (%s) — using headset.", msg)
                speak = getattr(tts, "speak", None)
                level_sink = getattr(hud, "level_sink", None) if hud is not None else None
                level_out = level_sink() if callable(level_sink) else None
                if callable(speak):
                    speak(
                        text,
                        streaming=False,
                        hud_level_out=level_out,
                        on_playback_start=_intro_playback_start,
                    )
        else:
            speak = getattr(tts, "speak", None)
            level_sink = getattr(hud, "level_sink", None) if hud is not None else None
            level_out = level_sink() if callable(level_sink) else None
            if callable(speak):
                speak(
                    text,
                    streaming=False,
                    hud_level_out=level_out,
                    on_playback_start=_intro_playback_start,
                )
        try:
            from mango.audio import release_mixer_before_mic

            release_mixer_before_mic()
        except Exception:
            logger.debug("release_mixer_after_intro noop", exc_info=True)
    except Exception:
        logger.exception("Startup intro failed — continuing without it.")
    finally:
        time.sleep(0.05)
        _state("listening")
        logger.info("MANGO_STATE: listening")

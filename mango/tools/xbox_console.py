"""Control an Xbox console through Xbox Live SmartGlass APIs."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from xbox.webapi.api.client import XboxLiveClient
from xbox.webapi.api.provider.smartglass.models import InputKeyType
from xbox.webapi.authentication.manager import AuthenticationManager
from xbox.webapi.authentication.models import OAuth2TokenResponse
from xbox.webapi.common.signed_session import SignedSession
from xbox.webapi.scripts import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

logger = logging.getLogger(__name__)


def description_for(owner: str) -> str:
    o = (owner or "the owner").strip() or "the owner"
    pos = f"{o}'s" if o.casefold() != "you" else "your"
    return (
        f"Control {pos} Xbox console through Xbox Live SmartGlass. Use this for requests to turn on "
        "the Xbox, check status, list consoles, list installed games, launch/start a game on the Xbox, "
        "go home, press a controller button, or power off the console."
    )


DESCRIPTION = description_for("the owner")

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "status",
                "list_consoles",
                "list_games",
                "wake",
                "launch_game",
                "home",
                "turn_off",
                "press_button",
            ],
            "description": "Xbox console action to perform.",
        },
        "game_name": {
            "type": "string",
            "description": "Game/app name to launch, e.g. Forza, Fortnite, Minecraft.",
        },
        "device_id": {
            "type": "string",
            "description": "Optional Xbox console device id. Defaults to XBOX_CONSOLE_ID or the first registered console.",
        },
        "button": {
            "type": "string",
            "enum": ["A", "B", "X", "Y", "Up", "Down", "Left", "Right", "Guide", "Menu", "View"],
            "description": "Controller button to press for press_button.",
        },
    },
    "required": ["action"],
    "additionalProperties": False,
}

_CACHE_PATH = Path.home() / ".mango" / "xbox_games_cache.json"


@dataclass
class _XboxContext:
    client: XboxLiveClient
    token_path: Path


@dataclass
class _InstalledGame:
    name: str
    one_store_product_id: str
    title_id: int | None = None


def _token_path() -> Path:
    raw = os.getenv("XBOX_TOKENS_PATH", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".mango" / "xbox_tokens.json"


def _setup_message() -> str:
    return (
        "Xbox is not authenticated yet. Run scripts\\setup-xbox-auth.ps1, sign in with the "
        "Microsoft account that owns the Xbox, then try again."
    )


def _enum_text(value: Any) -> str:
    return str(getattr(value, "value", value))


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").casefold()).strip()


def _score(query: str, candidate: str) -> float:
    q = _normalize(query)
    c = _normalize(candidate)
    if not q or not c:
        return 0.0
    if q == c:
        return 1.0
    if q in c or c in q:
        return 0.92
    return SequenceMatcher(None, q, c).ratio()


async def _context() -> _XboxContext | str:
    token_path = _token_path()
    if not token_path.is_file():
        return _setup_message()

    client_id = os.getenv("XBOX_CLIENT_ID", "").strip() or CLIENT_ID
    client_secret = os.getenv("XBOX_CLIENT_SECRET", "").strip() or CLIENT_SECRET
    redirect_uri = os.getenv("XBOX_REDIRECT_URI", "").strip() or REDIRECT_URI

    session = SignedSession()
    auth_mgr = AuthenticationManager(session, client_id, client_secret, redirect_uri)
    try:
        auth_mgr.oauth = OAuth2TokenResponse.model_validate_json(token_path.read_text(encoding="utf-8"))
        await auth_mgr.refresh_tokens()
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(auth_mgr.oauth.model_dump_json(), encoding="utf-8")
    except Exception as exc:
        await session.aclose()
        logger.warning("Xbox auth refresh failed: %s", exc)
        return f"Xbox authentication failed. Run scripts\\setup-xbox-auth.ps1 again. Details: {exc}"

    return _XboxContext(XboxLiveClient(auth_mgr), token_path)


async def _select_console(client: XboxLiveClient, requested_device_id: str | None = None) -> Any | str:
    consoles = (await client.smartglass.get_console_list()).result
    if not consoles:
        return "No registered Xbox consoles were found on this Microsoft account."

    preferred = (requested_device_id or os.getenv("XBOX_CONSOLE_ID", "")).strip()
    if preferred:
        for console in consoles:
            if console.id == preferred or console.name.casefold() == preferred.casefold():
                return console
        return f"Could not find Xbox console {preferred!r}. Use list_consoles to see available consoles."

    return consoles[0]


def _console_line(console: Any) -> str:
    return (
        f"{console.name} ({_enum_text(console.console_type)}) "
        f"id={console.id} power={_enum_text(console.power_state)} "
        f"remote_management={console.remote_management_enabled}"
    )


def _command_line(action: str, response: Any) -> str:
    status = getattr(response, "status", None)
    op_id = getattr(response, "op_id", None)
    ui_text = getattr(response, "ui_text", None)
    details = []
    if status is not None:
        details.append(f"status={status}")
    if op_id:
        details.append(f"op_id={op_id}")
    if ui_text:
        details.append(f"message={ui_text}")
    suffix = " " + " ".join(details) if details else ""
    return f"Xbox {action} command sent.{suffix}"


async def _list_consoles(ctx: _XboxContext) -> str:
    consoles = (await ctx.client.smartglass.get_console_list()).result
    if not consoles:
        return "No registered Xbox consoles were found."
    return "Xbox consoles:\n" + "\n".join(f"- {_console_line(c)}" for c in consoles)


async def _status(ctx: _XboxContext, device_id: str | None) -> str:
    console = await _select_console(ctx.client, device_id)
    if isinstance(console, str):
        return console
    status = await ctx.client.smartglass.get_console_status(console.id)
    return (
        f"Xbox {console.name}: power={_enum_text(status.power_state)}, "
        f"focus_app={status.focus_app_aumid or 'unknown'}, "
        f"playback={_enum_text(status.playback_state)}, "
        f"remote_management={status.remote_management_enabled}."
    )


async def _installed_games(ctx: _XboxContext, device_id: str | None) -> tuple[Any, list[_InstalledGame]] | str:
    console = await _select_console(ctx.client, device_id)
    if isinstance(console, str):
        return console
    try:
        resp = await ctx.client.smartglass._fetch_list("installedApps", {"deviceId": console.id})
        data = resp.json()
    except Exception as exc:
        logger.warning("Xbox installedApps raw fetch failed: %s", exc)
        return f"Could not read installed Xbox games from {console.name}: {exc}"

    raw_packages = data.get("result") if isinstance(data, dict) else None
    if not isinstance(raw_packages, list):
        return f"Xbox installed-apps response for {console.name} did not include a usable result list."

    games: list[_InstalledGame] = []
    for package in raw_packages:
        if not isinstance(package, dict):
            continue
        name = str(package.get("name") or "").strip()
        product_id = str(package.get("oneStoreProductId") or "").strip()
        if not name or not product_id:
            continue
        is_game = package.get("isGame")
        content_type = str(package.get("contentType") or "").casefold()
        if is_game is False or (is_game is None and "game" not in content_type and content_type):
            continue
        title_id_raw = package.get("titleId")
        try:
            title_id = int(title_id_raw) if title_id_raw is not None else None
        except (TypeError, ValueError):
            title_id = None
        games.append(_InstalledGame(name=name, one_store_product_id=product_id, title_id=title_id))

    games.sort(key=lambda p: _normalize(p.name))
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(
        json.dumps(
            {
                "device_id": console.id,
                "console_name": console.name,
                "games": [
                    {
                        "name": p.name,
                        "one_store_product_id": p.one_store_product_id,
                        "title_id": p.title_id,
                    }
                    for p in games
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return console, games


async def _list_games(ctx: _XboxContext, device_id: str | None) -> str:
    result = await _installed_games(ctx, device_id)
    if isinstance(result, str):
        return result
    console, games = result
    if not games:
        return f"No installed games were found on {console.name}."
    names = [p.name for p in games[:30]]
    more = f"\n...and {len(games) - 30} more." if len(games) > 30 else ""
    return f"Installed Xbox games on {console.name}:\n" + "\n".join(f"- {n}" for n in names) + more


async def _launch_game(ctx: _XboxContext, device_id: str | None, game_name: str | None) -> str:
    if not (game_name or "").strip():
        return "Missing game_name. Tell Mango which Xbox game to launch."
    result = await _installed_games(ctx, device_id)
    if isinstance(result, str):
        return result
    console, games = result
    scored = sorted(
        ((p, _score(game_name or "", p.name or "")) for p in games if p.one_store_product_id),
        key=lambda item: item[1],
        reverse=True,
    )
    if not scored or scored[0][1] < 0.45:
        return f"I could not find an installed Xbox game matching {game_name!r}. Try list_games first."
    close = [p for p, s in scored[:5] if s >= max(0.72, scored[0][1] - 0.08)]
    if len(close) > 1 and scored[0][1] < 0.94:
        return "Ambiguous Xbox game name. Candidates: " + ", ".join(p.name or "unknown" for p in close)
    game = scored[0][0]
    response = await ctx.client.smartglass.launch_app(console.id, game.one_store_product_id)
    return _command_line(f"launch {game.name} on {console.name}", response)


async def _run_async(
    action: str,
    *,
    game_name: str | None = None,
    device_id: str | None = None,
    button: str | None = None,
    _host_approved: bool = False,
) -> str:
    ctx = await _context()
    if isinstance(ctx, str):
        return ctx

    try:
        action_key = (action or "").strip().casefold()
        if action_key == "list_consoles":
            return await _list_consoles(ctx)
        if action_key == "status":
            return await _status(ctx, device_id)
        if action_key == "list_games":
            return await _list_games(ctx, device_id)

        console = await _select_console(ctx.client, device_id)
        if isinstance(console, str):
            return console

        if action_key == "wake":
            return _command_line(f"wake {console.name}", await ctx.client.smartglass.wake_up(console.id))
        if action_key == "home":
            return _command_line(f"go home on {console.name}", await ctx.client.smartglass.go_home(console.id))
        if action_key == "turn_off":
            if not _host_approved:
                return f"HOST_PENDING_XBOX_TURN_OFF: confirm powering off {console.name}."
            return _command_line(f"turn off {console.name}", await ctx.client.smartglass.turn_off(console.id))
        if action_key == "press_button":
            button_key = (button or "").strip()
            if not button_key:
                return "Missing button for Xbox press_button."
            try:
                button_value = InputKeyType(button_key)
            except ValueError:
                return f"Unknown Xbox button {button_key!r}."
            return _command_line(f"press {button_value.value} on {console.name}", await ctx.client.smartglass.press_button(console.id, button_value))
        if action_key == "launch_game":
            return await _launch_game(ctx, device_id, game_name)
        return f"Unknown Xbox action {action!r}."
    finally:
        await ctx.client._auth_mgr.session.aclose()


def run(
    action: str,
    *,
    game_name: str | None = None,
    device_id: str | None = None,
    button: str | None = None,
    _host_approved: bool = False,
) -> str:
    try:
        return asyncio.run(
            _run_async(
                action,
                game_name=game_name,
                device_id=device_id,
                button=button,
                _host_approved=_host_approved,
            )
        )
    except Exception as exc:
        logger.exception("xbox_console")
        return f"Xbox tool error: {exc}"

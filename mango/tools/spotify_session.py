"""Spotify user session: login (OAuth), logout, status for Web Playback mode."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

DESCRIPTION = (
    "Manage **Spotify user login** for **in-browser Web Playback** (no Spotify desktop app required). "
    "Actions: **login** — opens the browser; approve access; Mango saves tokens under ~/.mango/. "
    "**logout** — delete saved tokens. **status** — whether login looks valid. "
    "Requires **Premium** for playback. Set **MANGO_SPOTIFY_WEB_PLAYBACK=1** and redirect URI "
    "http://127.0.0.1:8765/callback on your Spotify app. Bookmark http://127.0.0.1:9876/ (or MANGO_SPOTIFY_PLAYER_PORT) "
    "for the web player tab when MANGO_SPOTIFY_AUTO_OPEN_PLAYER=0."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["login", "logout", "status"],
            "description": "login runs OAuth in the browser once; logout clears tokens; status summarizes login.",
        },
    },
    "required": ["action"],
    "additionalProperties": False,
}


def run(action: str) -> str:
    act = (action or "").strip().lower()
    import mango.integrations.spotify.spotify_user_auth as sua

    if act == "status":
        return sua.status_line()
    if act == "logout":
        sua.delete_token_data()
        try:
            import mango.integrations.spotify.spotify_player_server as sps

            sps.invalidate_device()
            sps.reset_player_browser_tab()
        except Exception:
            logger.debug("spotify session logout extras", exc_info=True)
        return "Spotify user tokens removed. Web player device cleared; next play can open the player tab again."
    if act == "login":
        return sua.run_login_flow()
    return f"Unknown action {action!r}. Use login, logout, or status."

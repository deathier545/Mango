"""Service interfaces/adapters for external integrations."""

from __future__ import annotations

from typing import Protocol

from mango.handoff_contracts import validate_handoff_payload


class SpotifyAuthService(Protocol):
    def get_valid_access_token(self) -> str | None: ...


class SpotifyDesktopPlaybackService(Protocol):
    def enabled(self) -> bool: ...
    def play_track_uri(self, access_token: str, uri: str) -> tuple[bool, str]: ...


class SpotifyUserAuthService:
    def get_valid_access_token(self) -> str | None:
        import mango.integrations.spotify.spotify_user_auth as sua

        return sua.get_valid_access_token()


class SpotifyDesktopApiService:
    def enabled(self) -> bool:
        import mango.integrations.spotify.spotify_desktop_api as sda

        return sda.desktop_connect_api_enabled()

    def play_track_uri(self, access_token: str, uri: str) -> tuple[bool, str]:
        import mango.integrations.spotify.spotify_desktop_api as sda

        return sda.play_track_uri(access_token, uri)


class DiscordVoiceService(Protocol):
    def run(self, **kwargs: object) -> str: ...


class XboxConsoleService(Protocol):
    def run(self, **kwargs: object) -> str: ...


class DiscordVoiceToolService:
    def run(self, **kwargs: object) -> str:
        from mango.tools import discord_voice

        return discord_voice.run(**kwargs)


class XboxConsoleToolService:
    def run(self, **kwargs: object) -> str:
        from mango.tools import xbox_console

        return xbox_console.run(**kwargs)


class HandoffRouterService:
    """Routes validated payloads to specialist domains."""

    @staticmethod
    def validate(domain: str, payload: dict[str, object]) -> tuple[bool, str]:
        return validate_handoff_payload(domain, payload)

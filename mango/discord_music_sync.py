"""Compatibility shim — prefer `mango.integrations.discord.discord_music_sync`."""
import sys as _sys

import mango.integrations.discord.discord_music_sync as _impl

_sys.modules[__name__] = _impl

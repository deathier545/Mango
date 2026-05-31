"""Compatibility shim — prefer `mango.integrations.discord.discord_voice_audio`."""
import sys as _sys

import mango.integrations.discord.discord_voice_audio as _impl

_sys.modules[__name__] = _impl

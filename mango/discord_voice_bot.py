"""Compatibility shim — prefer `mango.integrations.discord.discord_voice_bot`."""
import sys as _sys

import mango.integrations.discord.discord_voice_bot as _impl

_sys.modules[__name__] = _impl

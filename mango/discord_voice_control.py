"""Compatibility shim — prefer `mango.integrations.discord.discord_voice_control`."""
import sys as _sys

import mango.integrations.discord.discord_voice_control as _impl

_sys.modules[__name__] = _impl

"""Compatibility shim — prefer `mango.integrations.discord.discord_voice_client`."""
import sys as _sys

import mango.integrations.discord.discord_voice_client as _impl

_sys.modules[__name__] = _impl

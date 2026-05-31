"""Compatibility shim — prefer `mango.integrations.discord.discord_tts_client`."""
import sys as _sys

import mango.integrations.discord.discord_tts_client as _impl

_sys.modules[__name__] = _impl

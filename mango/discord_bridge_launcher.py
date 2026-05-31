"""Compatibility shim — prefer `mango.integrations.discord.discord_bridge_launcher`."""
import sys as _sys

import mango.integrations.discord.discord_bridge_launcher as _impl

_sys.modules[__name__] = _impl

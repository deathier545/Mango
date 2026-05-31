"""Compatibility shim — prefer `mango.integrations.spotify.spotify_desktop_api`."""
import sys as _sys

import mango.integrations.spotify.spotify_desktop_api as _impl

_sys.modules[__name__] = _impl

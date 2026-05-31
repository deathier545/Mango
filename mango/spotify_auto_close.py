"""Compatibility shim — prefer `mango.integrations.spotify.spotify_auto_close`."""
import sys as _sys

import mango.integrations.spotify.spotify_auto_close as _impl

_sys.modules[__name__] = _impl

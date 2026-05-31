"""Compatibility shim — prefer `mango.integrations.spotify.spotify_volume_duck`."""
import sys as _sys

import mango.integrations.spotify.spotify_volume_duck as _impl

_sys.modules[__name__] = _impl

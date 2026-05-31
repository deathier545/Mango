"""Compatibility shim — prefer `mango.integrations.spotify.spotify_track_resolver`."""
import sys as _sys

import mango.integrations.spotify.spotify_track_resolver as _impl

_sys.modules[__name__] = _impl

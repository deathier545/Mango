"""Compatibility shim — prefer `mango.integrations.spotify.spotify_playback_router`."""
import sys as _sys

import mango.integrations.spotify.spotify_playback_router as _impl

_sys.modules[__name__] = _impl

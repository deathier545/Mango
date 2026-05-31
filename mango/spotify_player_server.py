"""Compatibility shim — prefer `mango.integrations.spotify.spotify_player_server`."""
import sys as _sys

import mango.integrations.spotify.spotify_player_server as _impl

_sys.modules[__name__] = _impl

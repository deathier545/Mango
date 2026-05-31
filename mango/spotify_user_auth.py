"""Compatibility shim — prefer `mango.integrations.spotify.spotify_user_auth`."""
import sys as _sys

import mango.integrations.spotify.spotify_user_auth as _impl

_sys.modules[__name__] = _impl

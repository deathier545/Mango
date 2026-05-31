"""Compatibility shim — prefer `mango.integrations.spotify.spotify_uri_launcher`."""
import sys as _sys

import mango.integrations.spotify.spotify_uri_launcher as _impl

_sys.modules[__name__] = _impl

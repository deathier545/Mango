"""Compatibility shim — prefer `mango.integrations.spotify.spotify_windows_ui`."""
import sys as _sys

import mango.integrations.spotify.spotify_windows_ui as _impl

_sys.modules[__name__] = _impl

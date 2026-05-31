"""Compatibility shim — prefer `mango.desktop.globe_server`."""
import sys as _sys

import mango.desktop.globe_server as _impl

_sys.modules[__name__] = _impl

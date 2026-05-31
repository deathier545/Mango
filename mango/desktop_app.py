"""Compatibility shim — prefer `mango.desktop.desktop_app`."""
import sys as _sys

import mango.desktop.desktop_app as _impl

_sys.modules[__name__] = _impl

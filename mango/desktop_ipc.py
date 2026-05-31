"""Compatibility shim — prefer `mango.desktop.desktop_ipc`."""
import sys as _sys

import mango.desktop.desktop_ipc as _impl

_sys.modules[__name__] = _impl

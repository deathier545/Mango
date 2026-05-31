"""Compatibility shim — prefer `mango.smart.desktop_smart`."""
import sys as _sys

import mango.smart.desktop_smart as _impl

_sys.modules[__name__] = _impl

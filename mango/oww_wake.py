"""Compatibility shim — prefer `mango.wake.oww_wake`."""
import sys as _sys

import mango.wake.oww_wake as _impl

_sys.modules[__name__] = _impl

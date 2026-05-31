"""Compatibility shim — prefer `mango.smart.smart_routines`."""
import sys as _sys

import mango.smart.smart_routines as _impl

_sys.modules[__name__] = _impl

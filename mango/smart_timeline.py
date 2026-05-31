"""Compatibility shim — prefer `mango.smart.smart_timeline`."""
import sys as _sys

import mango.smart.smart_timeline as _impl

_sys.modules[__name__] = _impl

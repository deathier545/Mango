"""Compatibility shim — prefer `mango.smart.smart_store`."""
import sys as _sys

import mango.smart.smart_store as _impl

_sys.modules[__name__] = _impl

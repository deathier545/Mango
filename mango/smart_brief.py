"""Compatibility shim — prefer `mango.smart.smart_brief`."""
import sys as _sys

import mango.smart.smart_brief as _impl

_sys.modules[__name__] = _impl

"""Compatibility shim — prefer `mango.wake.wake_capture`."""
import sys as _sys

import mango.wake.wake_capture as _impl

_sys.modules[__name__] = _impl

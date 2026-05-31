"""Compatibility shim — prefer `mango.wake.wake_listener`."""
import sys as _sys

import mango.wake.wake_listener as _impl

_sys.modules[__name__] = _impl

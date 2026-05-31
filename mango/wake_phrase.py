"""Compatibility shim — prefer `mango.wake.wake_phrase`."""
import sys as _sys

import mango.wake.wake_phrase as _impl

_sys.modules[__name__] = _impl

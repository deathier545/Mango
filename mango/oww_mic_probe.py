"""Compatibility shim — prefer `mango.wake.oww_mic_probe`."""
import sys as _sys

import mango.wake.oww_mic_probe as _impl

_sys.modules[__name__] = _impl

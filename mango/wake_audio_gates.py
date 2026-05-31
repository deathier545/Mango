"""Compatibility shim — prefer `mango.wake.wake_audio_gates`."""
import sys as _sys

import mango.wake.wake_audio_gates as _impl

_sys.modules[__name__] = _impl

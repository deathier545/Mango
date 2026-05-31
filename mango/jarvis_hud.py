"""Compatibility shim — use ``mango.desktop.mango_hud``."""
import sys as _sys

import mango.desktop.mango_hud as _impl

_sys.modules[__name__] = _impl

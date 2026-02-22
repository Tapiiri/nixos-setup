"""Compatibility shim for the historical import path.

The implementation now lives in scripts_py.lib.schemastore.
"""

from __future__ import annotations

import sys as _sys

from scripts_py.lib import schemastore as _impl

_sys.modules[__name__] = _impl

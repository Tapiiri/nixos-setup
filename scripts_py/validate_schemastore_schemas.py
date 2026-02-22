"""Compatibility shim for the historical import path.

The implementation now lives in scripts_py.cli.validate_schemastore_schemas.
"""

from __future__ import annotations

import sys as _sys

from scripts_py.cli import validate_schemastore_schemas as _impl

_sys.modules[__name__] = _impl

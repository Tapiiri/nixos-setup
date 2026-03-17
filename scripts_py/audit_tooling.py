"""Compatibility shim for the historical import path.

The implementation now lives in scripts_py.cli.audit_tooling.
"""

from __future__ import annotations

import sys as _sys

from scripts_py.cli import audit_tooling as _impl

_sys.modules[__name__] = _impl

"""Compatibility shim for the historical import path.

The implementation now lives in scripts_py.cli.sync_vscode_settings.
"""

from __future__ import annotations

import sys as _sys

from scripts_py.cli import sync_vscode_settings as _impl

_sys.modules[__name__] = _impl

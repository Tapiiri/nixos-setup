"""Compatibility shim for the historical import path.

The implementation now lives in scripts_py.lib.password_manager.
"""

from __future__ import annotations

from scripts_py.lib import password_manager as _impl

CheckResult = _impl.CheckResult
LastPassBackend = _impl.LastPassBackend
PasswordManagerBackend = _impl.PasswordManagerBackend

check_password_manager_logged_in = _impl.check_password_manager_logged_in
get_password_manager_backend = _impl.get_password_manager_backend

__all__ = [
    "CheckResult",
    "LastPassBackend",
    "PasswordManagerBackend",
    "check_password_manager_logged_in",
    "get_password_manager_backend",
]

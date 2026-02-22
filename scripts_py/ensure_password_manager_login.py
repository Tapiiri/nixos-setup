"""Compatibility shim for the historical import path.

The implementation now lives in scripts_py.cli.ensure_password_manager_login.
"""

from __future__ import annotations

from scripts_py.cli import ensure_password_manager_login as _impl

main = _impl.main
parse_args = _impl.parse_args

__all__ = [
    "main",
    "parse_args",
]


if __name__ == "__main__":
    raise SystemExit(main())

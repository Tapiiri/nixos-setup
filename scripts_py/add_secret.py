"""Compatibility shim for the historical import path.

The implementation now lives in scripts_py.cli.add_secret.
"""

from __future__ import annotations

from scripts_py.cli import add_secret as _impl

AddSecretOptions = _impl.AddSecretOptions

add_secret_to_lastpass = _impl.add_secret_to_lastpass
add_secret_to_password_manager = _impl.add_secret_to_password_manager
add_secret_to_secretspec = _impl.add_secret_to_secretspec
main = _impl.main
parse_args = _impl.parse_args

__all__ = [
    "AddSecretOptions",
    "add_secret_to_lastpass",
    "add_secret_to_password_manager",
    "add_secret_to_secretspec",
    "main",
    "parse_args",
]


if __name__ == "__main__":
    raise SystemExit(main())

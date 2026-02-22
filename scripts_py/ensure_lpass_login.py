"""Compatibility shim for the historical import path.

The implementation now lives in scripts_py.cli.ensure_lpass_login.
"""

from __future__ import annotations

from scripts_py.cli import ensure_lpass_login as _impl

CheckResult = _impl.CheckResult

check_lpass_logged_in = _impl.check_lpass_logged_in
ensure_lpass_logged_in_or_exit = _impl.ensure_lpass_logged_in_or_exit
main = _impl.main
warn_if_lpass_not_logged_in = _impl.warn_if_lpass_not_logged_in

__all__ = [
    "CheckResult",
    "check_lpass_logged_in",
    "ensure_lpass_logged_in_or_exit",
    "main",
    "warn_if_lpass_not_logged_in",
]


if __name__ == "__main__":
    raise SystemExit(main())

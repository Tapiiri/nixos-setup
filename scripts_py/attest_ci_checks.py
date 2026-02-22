"""Compatibility shim for the historical import path.

The implementation now lives in scripts_py.ci.attest_ci_checks.
"""

from __future__ import annotations

from scripts_py.ci import attest_ci_checks as _impl

DEFAULT_NOTES_REF = _impl.DEFAULT_NOTES_REF
Options = _impl.Options
SubprocessRunner = _impl.SubprocessRunner

attest_ci_checks = _impl.attest_ci_checks
main = _impl.main
parse_args = _impl.parse_args

__all__ = [
    "DEFAULT_NOTES_REF",
    "Options",
    "SubprocessRunner",
    "attest_ci_checks",
    "main",
    "parse_args",
]


if __name__ == "__main__":
    raise SystemExit(main())

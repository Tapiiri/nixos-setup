"""Compatibility shim for the historical import path.

The implementation now lives in scripts_py.ci.check_ci_attestation.
"""

from __future__ import annotations

from scripts_py.ci import check_ci_attestation as _impl

DEFAULT_NOTES_REF = _impl.DEFAULT_NOTES_REF
Options = _impl.Options
SimpleCompletedProcess = _impl.SimpleCompletedProcess
SubprocessRunner = _impl.SubprocessRunner

has_attestation = _impl.has_attestation
main = _impl.main
parse_args = _impl.parse_args

__all__ = [
    "DEFAULT_NOTES_REF",
    "Options",
    "SimpleCompletedProcess",
    "SubprocessRunner",
    "has_attestation",
    "main",
    "parse_args",
]


if __name__ == "__main__":
    raise SystemExit(main())

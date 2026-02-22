"""Compatibility shim for the historical import path.

The implementation now lives in scripts_py.ci.ci_attestation_gate.
"""

from __future__ import annotations

from scripts_py.ci import ci_attestation_gate as _impl

DEFAULT_NOTES_REF = _impl.DEFAULT_NOTES_REF
Options = _impl.Options
SubprocessRunner = _impl.SubprocessRunner

compute_skip = _impl.compute_skip
main = _impl.main
parse_args = _impl.parse_args
should_consider_skipping = _impl.should_consider_skipping
write_github_output = _impl.write_github_output

# Tests reference ci_attestation_gate.subprocess.CalledProcessError.
subprocess = _impl.subprocess

__all__ = [
    "DEFAULT_NOTES_REF",
    "Options",
    "SubprocessRunner",
    "compute_skip",
    "main",
    "parse_args",
    "should_consider_skipping",
    "subprocess",
    "write_github_output",
]


if __name__ == "__main__":
    raise SystemExit(main())

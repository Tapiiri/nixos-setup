"""Generic cached-check CLI.

Usage::

    cached-check --name ruff \\
                 --glob 'scripts_py/**/*.py' --glob 'tests/**/*.py' \\
                 --file pyproject.toml \\
                 -- ruff check scripts_py tests

Computes a composite hash of the declared inputs, skips the command if a
passing attestation exists, otherwise runs the command and stores the result.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Protocol, Sequence, TextIO

from scripts_py.lib.cached_check import (
    compute_input_hash,
    gc_stale,
    invalidate,
    lookup,
    store,
)
from scripts_py.lib.utils import log_info, log_warn
from scripts_py.repo.context import repo_root_from_script_path

_STATE_REL = Path(".devenv") / "state"


# ------------------------------------------------------------------
# Subprocess abstraction (testable)
# ------------------------------------------------------------------


class CmdRunner(Protocol):
    """Thin subprocess interface for dependency injection in tests."""

    def run_passthrough(self, argv: Sequence[str], *, cwd: str) -> int:
        """Run a command with inherited stdio, return exit code."""
        ...  # pragma: no cover


class SubprocessRunner:
    """Production implementation."""

    def run_passthrough(self, argv: Sequence[str], *, cwd: str) -> int:
        return subprocess.run(list(argv), cwd=cwd).returncode


# ------------------------------------------------------------------
# Core logic
# ------------------------------------------------------------------


def run_cached_check(
    *,
    name: str,
    globs: tuple[str, ...],
    files: tuple[str, ...],
    command: list[str],
    repo_root: Path,
    runner: CmdRunner,
    force: bool = False,
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> int:
    """Check the attestation cache and run the command if needed."""
    _out = out or sys.stdout
    _err = err or sys.stderr

    state_dir = repo_root / _STATE_REL
    input_hash = compute_input_hash(repo_root, globs=globs, files=files)

    if not force:
        cached = lookup(state_dir, name, input_hash)
        if cached is True:
            log_info(f"[cached-check:{name}] Inputs unchanged — skipping.", out=_out)
            return 0
        if cached is False:
            log_warn(f"[cached-check:{name}] Previous run failed — re-running.", err=_err)

    log_info(f"[cached-check:{name}] Running: {' '.join(command)}", out=_out)
    t0 = time.time()
    rc = runner.run_passthrough(command, cwd=str(repo_root))
    elapsed = time.time() - t0

    store(state_dir, name, input_hash, ok=(rc == 0), elapsed=elapsed)

    if rc == 0:
        log_info(f"[cached-check:{name}] Passed in {elapsed:.1f}s — attested.", out=_out)
    else:
        log_warn(f"[cached-check:{name}] FAILED in {elapsed:.1f}s — fail-attested.", err=_err)

    return rc


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------


def main(
    argv: list[str] | None = None,
    runner: CmdRunner | None = None,
) -> int:
    """Parse CLI args and dispatch."""

    parser = argparse.ArgumentParser(
        description="Run a command with input-hash attestation caching.",
    )
    parser.add_argument("--name", required=True, help="Unique check name (e.g. 'ruff').")
    parser.add_argument(
        "--glob",
        action="append",
        default=[],
        dest="globs",
        help="Glob pattern for input files (repeatable).",
    )
    parser.add_argument(
        "--file",
        action="append",
        default=[],
        dest="files",
        help="Explicit input file path relative to repo root (repeatable).",
    )
    parser.add_argument("--force", action="store_true", help="Ignore cache; always run.")
    parser.add_argument("--gc", action="store_true", help="GC stale attestations and exit.")
    parser.add_argument(
        "--invalidate", action="store_true", help="Remove all attestations and exit."
    )
    parser.add_argument("command", nargs="*", help="Command to run (after --).")

    args = parser.parse_args(argv)

    try:
        repo_root = repo_root_from_script_path(Path(__file__))
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    state_dir = repo_root / _STATE_REL

    if args.gc:
        n = gc_stale(state_dir, args.name)
        print(f"Removed {n} stale {args.name} attestation(s).", file=sys.stderr)
        return 0

    if args.invalidate:
        n = invalidate(state_dir, args.name)
        print(f"Removed {n} {args.name} attestation(s).", file=sys.stderr)
        return 0

    if not args.command:
        parser.error("No command specified (use -- before the command).")

    return run_cached_check(
        name=args.name,
        globs=tuple(args.globs),
        files=tuple(args.files),
        command=args.command,
        repo_root=repo_root,
        runner=runner or SubprocessRunner(),
        force=args.force,
    )

"""Run ``nix flake check --no-build`` with attestation caching.

In pre-commit mode (default), if the composite hash of all ``.nix`` files
and ``flake.lock`` matches a passing attestation, the hook exits instantly.
Otherwise it runs the check and stores the result.

Flags:

* ``--force``      — always run the check, ignoring cached attestations.
* ``--gc``         — garbage-collect stale attestations and exit.
* ``--invalidate`` — remove all cached results and exit.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Protocol, Sequence

from scripts_py.lib.nix_check_attestation import (
    compute_nix_hash,
    gc_nix_stale,
    invalidate_nix_attestations,
    lookup_nix_attestation,
    store_nix_attestation,
)
from scripts_py.lib.utils import log_info, log_warn
from scripts_py.repo.context import repo_root_from_script_path

# Where attestation data lives, relative to repo root.
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
        import subprocess

        return subprocess.run(list(argv), cwd=cwd).returncode


# ------------------------------------------------------------------
# Core logic
# ------------------------------------------------------------------


def run_cached_nix_check(
    *,
    repo_root: Path,
    runner: CmdRunner,
    force: bool = False,
    out=None,
    err=None,
) -> int:
    """Check the attestation cache and run ``nix flake check --no-build`` if needed."""
    if out is None:
        out = sys.stdout
    if err is None:
        err = sys.stderr

    state_dir = repo_root / _STATE_REL
    nix_hash = compute_nix_hash(repo_root)

    # Check cache (unless --force).
    if not force:
        cached = lookup_nix_attestation(state_dir, nix_hash)
        if cached is True:
            log_info("[cached-nix-check] Nix files unchanged — skipping.", out=out)
            return 0
        if cached is False:
            log_warn("[cached-nix-check] Previous check failed — re-running.", err=err)

    # Run the actual check.
    argv = ["nix", "flake", "check", "--no-build"]
    log_info(f"[cached-nix-check] Running: {' '.join(argv)}", out=out)
    t0 = time.time()
    rc = runner.run_passthrough(argv, cwd=str(repo_root))
    elapsed = time.time() - t0

    # Store result.
    store_nix_attestation(state_dir, nix_hash, ok=(rc == 0), elapsed=elapsed)

    if rc == 0:
        log_info(
            f"[cached-nix-check] Passed in {elapsed:.1f}s — attested.",
            out=out,
        )
    else:
        log_warn(
            f"[cached-nix-check] FAILED in {elapsed:.1f}s — fail-attested.",
            err=err,
        )

    return rc


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------


def main(
    argv: list[str] | None = None,
    runner: CmdRunner | None = None,
) -> int:
    """Parse CLI args and dispatch."""

    import argparse

    parser = argparse.ArgumentParser(
        description="Run nix flake check with attestation caching.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore cached attestations; always run the check.",
    )
    parser.add_argument(
        "--gc",
        action="store_true",
        help="Garbage-collect stale attestations and exit.",
    )
    parser.add_argument(
        "--invalidate",
        action="store_true",
        help="Remove all cached attestations and exit.",
    )
    args = parser.parse_args(argv)

    try:
        repo_root = repo_root_from_script_path(Path(__file__))
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    state_dir = repo_root / _STATE_REL

    if args.gc:
        n = gc_nix_stale(state_dir)
        print(f"Removed {n} stale nix attestation(s).", file=sys.stderr)
        return 0

    if args.invalidate:
        n = invalidate_nix_attestations(state_dir)
        print(f"Removed {n} nix attestation(s).", file=sys.stderr)
        return 0

    if runner is None:
        runner = SubprocessRunner()

    return run_cached_nix_check(
        repo_root=repo_root,
        runner=runner,
        force=args.force,
    )

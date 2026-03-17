"""Run pytest with file-level attestation caching.

Two modes:

* **Pre-commit** (default) — checks staged files.  If every affected test has
  a fresh passing attestation the hook exits immediately.  Otherwise runs
  pytest on the unattested subset and records attestations.

* **Watch** (``--watch``) — for the background devenv process.  Checks both
  staged *and* unstaged changes, runs unattested tests, and stores results.

Common flags:

* ``--force`` — ignore the cache and always invoke pytest.
* ``--gc``    — garbage-collect stale attestations and exit.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Protocol, Sequence

from scripts_py.lib.depmap import (
    GLOBAL_CONFIG_FILES,
    affected_tests,
    build_import_graph,
    transitive_deps,
)
from scripts_py.lib.test_attestation import (
    check_all_attested,
    compute_composite_hash,
    gc_stale,
    invalidate_all,
    store_attestation,
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

    def run_capture(self, argv: Sequence[str], *, cwd: str) -> tuple[int, str]:
        """Run a command, return (returncode, stdout)."""
        ...  # pragma: no cover

    def run_passthrough(self, argv: Sequence[str], *, cwd: str) -> int:
        """Run a command with inherited stdio, return exit code."""
        ...  # pragma: no cover


class SubprocessRunner:
    """Production implementation — delegates to ``subprocess``."""

    def run_capture(self, argv: Sequence[str], *, cwd: str) -> tuple[int, str]:
        r = subprocess.run(list(argv), cwd=cwd, capture_output=True, text=True)
        return r.returncode, r.stdout

    def run_passthrough(self, argv: Sequence[str], *, cwd: str) -> int:
        return subprocess.run(list(argv), cwd=cwd).returncode


# ------------------------------------------------------------------
# Git helpers
# ------------------------------------------------------------------


def _changed_py_files(
    runner: CmdRunner,
    repo_root: Path,
    *,
    staged_only: bool = True,
) -> set[Path]:
    """Return the set of changed ``.py`` files (absolute paths)."""
    flags = ["--cached"] if staged_only else []
    _, stdout = runner.run_capture(
        ["git", "diff", *flags, "--name-only", "--diff-filter=ACMR", "--", "*.py"],
        cwd=str(repo_root),
    )
    files: set[Path] = set()
    for line in stdout.splitlines():
        line = line.strip()
        if line:
            files.add((repo_root / line).resolve())
    return files


def _global_configs_changed(
    runner: CmdRunner,
    repo_root: Path,
    *,
    staged_only: bool = True,
) -> bool:
    """Return True if any global config file has staged (or unstaged) changes."""
    flags = ["--cached"] if staged_only else []
    patterns = [f"*{cfg}" for cfg in GLOBAL_CONFIG_FILES]
    _, stdout = runner.run_capture(
        ["git", "diff", *flags, "--name-only", "--diff-filter=ACMR", "--"] + patterns,
        cwd=str(repo_root),
    )
    return bool(stdout.strip())


# ------------------------------------------------------------------
# Core logic
# ------------------------------------------------------------------


def run_cached_pytest(
    *,
    repo_root: Path,
    runner: CmdRunner,
    force: bool = False,
    watch_mode: bool = False,
    extra_pytest_args: Sequence[str] = (),
    out=None,
    err=None,
) -> int:
    """Main implementation.

    Returns the exit code (0 = success, non-zero = test failure or error).
    """
    if out is None:
        out = sys.stdout
    if err is None:
        err = sys.stderr

    state_dir = repo_root / _STATE_REL

    # 1. Build the import graph.
    graph = build_import_graph(repo_root)

    # 2. Determine changed files.
    staged_only = not watch_mode
    changed = _changed_py_files(runner, repo_root, staged_only=staged_only)
    if watch_mode:
        # In watch mode also include staged changes.
        changed |= _changed_py_files(runner, repo_root, staged_only=True)

    # Check for global config changes — if any, invalidate all attestations.
    if _global_configs_changed(runner, repo_root, staged_only=staged_only):
        log_info("[cached-pytest] Global config changed — invalidating all attestations.", out=out)
        invalidate_all(state_dir)
        changed |= {repo_root / cfg for cfg in GLOBAL_CONFIG_FILES if (repo_root / cfg).is_file()}

    # If no Python files changed (and no global configs), nothing to do.
    if not changed:
        log_info("[cached-pytest] No Python files changed.", out=out)
        return 0

    # 3. Determine which tests are affected.
    affected = affected_tests(graph, changed)
    if not affected:
        log_info("[cached-pytest] No tests affected by changes.", out=out)
        return 0

    # 4. Check attestation cache (unless --force).
    if force:
        to_run = affected
    else:
        attested, to_run = check_all_attested(state_dir, affected, graph, repo_root)
        if attested and not to_run:
            log_info(
                f"[cached-pytest] All {len(attested)} affected test(s) cached — skipping.",
                out=out,
            )
            return 0
        if attested:
            log_info(
                f"[cached-pytest] {len(attested)} test(s) cached, {len(to_run)} need running.",
                out=out,
            )

    # 5. Run pytest on the unattested test files.
    test_paths = sorted(str(t) for t in to_run)
    pytest_argv = ["python", "-m", "pytest", "-q", *test_paths, *list(extra_pytest_args)]

    log_info(f"[cached-pytest] Running: {' '.join(pytest_argv)}", out=out)
    t0 = time.time()
    rc = runner.run_passthrough(pytest_argv, cwd=str(repo_root))
    elapsed = time.time() - t0

    # 6. Store attestations.
    for tf in to_run:
        deps = transitive_deps(graph, tf)
        ch = compute_composite_hash(tf, deps, repo_root)
        store_attestation(
            state_dir,
            tf,
            ch,
            ok=(rc == 0),
            elapsed=elapsed,
        )

    if rc == 0:
        log_info(
            f"[cached-pytest] {len(to_run)} test(s) passed in {elapsed:.1f}s — attested.",
            out=out,
        )
    else:
        log_warn(
            f"[cached-pytest] {len(to_run)} test(s) FAILED in {elapsed:.1f}s — fail-attested.",
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
    """Parse CLI args and dispatch to ``run_cached_pytest``."""

    import argparse

    parser = argparse.ArgumentParser(
        description="Run pytest with file-level attestation caching.",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch mode: include both staged and unstaged changes.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore cached attestations; always run pytest.",
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
        n = gc_stale(state_dir)
        print(f"Removed {n} stale attestation(s).", file=sys.stderr)
        return 0

    if args.invalidate:
        n = invalidate_all(state_dir)
        print(f"Removed {n} attestation(s).", file=sys.stderr)
        return 0

    if runner is None:
        runner = SubprocessRunner()

    # Forward PYTEST_ADDOPTS for --lf integration with pre-commit.
    extra: list[str] = []
    addopts = os.environ.get("PYTEST_ADDOPTS", "")
    if addopts:
        extra.extend(addopts.split())

    return run_cached_pytest(
        repo_root=repo_root,
        runner=runner,
        force=args.force,
        watch_mode=args.watch,
        extra_pytest_args=extra,
    )

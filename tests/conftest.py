"""Pytest plugin: write a generic cached-check attestation after each session.

When VS Code's Test Explorer (or any pytest invocation) runs tests, this
plugin records a "pytest" attestation in the devenv state directory using
the same generic ``cached_check`` system as all other checks.  The
pre-commit hook (``scripts/cached-check --name pytest ...``) can then skip
re-running tests that already have a fresh passing attestation.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Initialise per-file result tracking on the config object."""
    config._attestation_file_results = {}  # type: ignore[attr-defined]  # Path -> bool


def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> None:
    """Record per-file pass/fail during the ``call`` phase."""
    if call.when != "call":
        return

    test_file = Path(getattr(item, "path", item.fspath)).resolve()
    results: dict[Path, bool] = item.config._attestation_file_results  # type: ignore[attr-defined]

    if call.excinfo is not None:
        results[test_file] = False
    elif results.get(test_file) is not False:  # pyright: ignore[reportUnknownMemberType]
        results[test_file] = True


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Write a "pytest" attestation after the session ends if all tests passed."""
    results: dict[Path, bool] = getattr(session.config, "_attestation_file_results", {})
    if not results:
        return

    # Only attest a passing result when every collected test file passed.
    all_passed = all(results.values())

    try:
        from scripts_py.lib.cached_check import compute_input_hash, store
        from scripts_py.repo.context import repo_root_from_script_path
    except ImportError:
        return

    try:
        repo_root = repo_root_from_script_path(Path(__file__))
    except FileNotFoundError:
        return

    state_dir = repo_root / ".devenv" / "state"

    # Use the same globs/files as the "pytest" CheckDef in KNOWN_CHECKS.
    input_hash = compute_input_hash(
        repo_root,
        globs=("scripts_py/**/*.py", "tests/**/*.py"),
        files=("pyproject.toml", "devenv.nix"),
    )
    store(state_dir, "pytest", input_hash, ok=all_passed)

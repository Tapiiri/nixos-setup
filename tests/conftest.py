"""Pytest plugin: write file-level test attestations after each session.

When VS Code's Test Explorer (or any pytest invocation) runs tests, this
plugin records per-file pass/fail attestations in the devenv state directory.
The pre-commit hook (``scripts/cached-pytest``) can then skip re-running
tests that already have a fresh passing attestation.

The ``pucelle.run-on-save`` VS Code extension triggers ``testing.runAll`` on
every ``.py`` save, which feeds through Test Explorer and ends up here.
This gives you inline pass/fail gutter decorations *and* instant pre-commit
resolution — no separate background watcher needed.
"""

from __future__ import annotations

from pathlib import Path


def pytest_configure(config):
    """Initialise per-file result tracking on the config object."""
    config._attestation_file_results = {}  # Path -> bool


def pytest_runtest_makereport(item, call):
    """Record per-file pass/fail during the ``call`` phase."""
    if call.when != "call":
        return

    # item.path is pathlib.Path (pytest >= 7); item.fspath is the legacy py.path.
    test_file = Path(getattr(item, "path", item.fspath)).resolve()
    results = item.config._attestation_file_results

    if call.excinfo is not None:
        # Any failure in a file marks the whole file as failed.
        results[test_file] = False
    elif results.get(test_file) is not False:
        # Only mark as passed if not already failed by another test in the file.
        results[test_file] = True


def pytest_sessionfinish(session, exitstatus):
    """Write attestations for every collected test file after the session ends."""
    results = getattr(session.config, "_attestation_file_results", {})
    if not results:
        return

    # Lazy-import to keep the plugin lightweight and avoid import errors when
    # running outside the repo (e.g. in CI containers without scripts_py).
    try:
        from scripts_py.lib.depmap import build_import_graph, transitive_deps
        from scripts_py.lib.test_attestation import compute_composite_hash, store_attestation
        from scripts_py.repo.context import repo_root_from_script_path
    except ImportError:
        return

    try:
        repo_root = repo_root_from_script_path(Path(__file__))
    except FileNotFoundError:
        return

    state_dir = repo_root / ".devenv" / "state"
    graph = build_import_graph(repo_root)

    for test_file, ok in results.items():
        deps = transitive_deps(graph, test_file)
        composite_hash = compute_composite_hash(test_file, deps, repo_root)
        store_attestation(state_dir, test_file, composite_hash, ok=ok)

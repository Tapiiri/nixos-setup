"""Tests for scripts_py.cli.cached_pytest — cached pytest runner."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from typing import Sequence

from scripts_py.cli.cached_pytest import run_cached_pytest
from scripts_py.lib.depmap import build_import_graph, transitive_deps
from scripts_py.lib.test_attestation import (
    CACHE_DIR_NAME,
    compute_composite_hash,
    store_attestation,
)

# ------------------------------------------------------------------
# Fake runner
# ------------------------------------------------------------------


class FakeRunner:
    """Records commands instead of executing them."""

    def __init__(
        self,
        *,
        git_diff_staged: str = "",
        git_diff_unstaged: str = "",
        git_diff_global_staged: str = "",
        git_diff_global_unstaged: str = "",
        pytest_rc: int = 0,
    ) -> None:
        self._git_diff_staged = git_diff_staged
        self._git_diff_unstaged = git_diff_unstaged
        self._git_diff_global_staged = git_diff_global_staged
        self._git_diff_global_unstaged = git_diff_global_unstaged
        self._pytest_rc = pytest_rc
        self.passthrough_calls: list[list[str]] = []

    def run_capture(self, argv: Sequence[str], *, cwd: str) -> tuple[int, str]:
        argv_list = list(argv)
        # Distinguish git diff calls by flags.
        if "git" in argv_list and "diff" in argv_list:
            is_cached = "--cached" in argv_list
            # Global-config queries use patterns like *pyproject.toml / *devenv.nix
            # (not *.py which is the regular Python file diff).
            is_global = any(a.startswith("*") and not a.startswith("*.") for a in argv_list)
            if is_global:
                if is_cached:
                    return 0, self._git_diff_global_staged
                return 0, self._git_diff_global_unstaged
            if is_cached:
                return 0, self._git_diff_staged
            return 0, self._git_diff_unstaged
        return 0, ""

    def run_passthrough(self, argv: Sequence[str], *, cwd: str) -> int:
        self.passthrough_calls.append(list(argv))
        return self._pytest_rc


# ------------------------------------------------------------------
# Helpers for creating a mini repo
# ------------------------------------------------------------------


def _make_repo(root: Path) -> None:
    """Create a minimal repo structure with scripts_py and tests."""
    sp = root / "scripts_py" / "lib"
    sp.mkdir(parents=True)
    (root / "scripts_py" / "__init__.py").write_text("")
    (sp / "__init__.py").write_text("")
    (sp / "utils.py").write_text("# leaf\n")
    (sp / "foo.py").write_text("from scripts_py.lib.utils import log_info\n")

    tests = root / "tests"
    tests.mkdir()
    (tests / "__init__.py").write_text("")
    (tests / "test_foo.py").write_text("from scripts_py.lib.foo import something\n")
    (tests / "test_utils.py").write_text("from scripts_py.lib.utils import log_info\n")

    # Global configs.
    (root / "pyproject.toml").write_text("[tool.pytest]")
    (root / "devenv.nix").write_text("{}")


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestSkipsWhenAllAttested(unittest.TestCase):
    def test_skips_when_cache_fresh(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_repo(root)
            state_dir = root / ".devenv" / "state"

            graph = build_import_graph(root)
            test_foo = root / "tests" / "test_foo.py"

            # Pre-populate cache for test_foo.py.
            deps = transitive_deps(graph, test_foo)
            ch = compute_composite_hash(test_foo, deps, root)
            store_attestation(state_dir, test_foo, ch, ok=True, elapsed=0.5)

            runner = FakeRunner(
                git_diff_staged="scripts_py/lib/foo.py\n",
            )
            out, err = io.StringIO(), io.StringIO()

            rc = run_cached_pytest(
                repo_root=root,
                runner=runner,
                out=out,
                err=err,
            )

            self.assertEqual(rc, 0)
            # pytest should not have been invoked.
            self.assertEqual(runner.passthrough_calls, [])
            self.assertIn("cached", out.getvalue().lower())


class TestRunsPytestWhenUnattested(unittest.TestCase):
    def test_runs_pytest_on_uncached(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_repo(root)

            runner = FakeRunner(
                git_diff_staged="scripts_py/lib/foo.py\n",
                pytest_rc=0,
            )
            out, err = io.StringIO(), io.StringIO()

            rc = run_cached_pytest(
                repo_root=root,
                runner=runner,
                out=out,
                err=err,
            )

            self.assertEqual(rc, 0)
            # pytest should have been called.
            self.assertEqual(len(runner.passthrough_calls), 1)
            self.assertIn("pytest", runner.passthrough_calls[0][2])


class TestStoresAttestationOnSuccess(unittest.TestCase):
    def test_cache_populated_after_pass(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_repo(root)
            state_dir = root / ".devenv" / "state"

            runner = FakeRunner(
                git_diff_staged="scripts_py/lib/foo.py\n",
                pytest_rc=0,
            )

            run_cached_pytest(
                repo_root=root,
                runner=runner,
                out=io.StringIO(),
                err=io.StringIO(),
            )

            # Cache should have an entry.
            cache = state_dir / CACHE_DIR_NAME
            entries = list(cache.glob("*.json"))
            self.assertGreater(len(entries), 0)


class TestStoresFailAttestation(unittest.TestCase):
    def test_cache_records_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_repo(root)

            runner = FakeRunner(
                git_diff_staged="scripts_py/lib/foo.py\n",
                pytest_rc=1,
            )

            rc = run_cached_pytest(
                repo_root=root,
                runner=runner,
                out=io.StringIO(),
                err=io.StringIO(),
            )

            self.assertEqual(rc, 1)

            # Cache should have a fail entry — second run should also fail
            # without invoking pytest again.
            runner2 = FakeRunner(
                git_diff_staged="scripts_py/lib/foo.py\n",
            )
            run_cached_pytest(
                repo_root=root,
                runner=runner2,
                out=io.StringIO(),
                err=io.StringIO(),
            )
            # Cached fail → still need to run (unattested for "pass"),
            # because lookup returns False for fails ≠ True.
            self.assertEqual(len(runner2.passthrough_calls), 1)


class TestForceIgnoresCache(unittest.TestCase):
    def test_force_flag(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_repo(root)
            state_dir = root / ".devenv" / "state"

            graph = build_import_graph(root)
            test_foo = root / "tests" / "test_foo.py"
            deps = transitive_deps(graph, test_foo)
            ch = compute_composite_hash(test_foo, deps, root)
            store_attestation(state_dir, test_foo, ch, ok=True, elapsed=0.5)

            runner = FakeRunner(
                git_diff_staged="scripts_py/lib/foo.py\n",
                pytest_rc=0,
            )
            out = io.StringIO()

            rc = run_cached_pytest(
                repo_root=root,
                runner=runner,
                force=True,
                out=out,
                err=io.StringIO(),
            )

            self.assertEqual(rc, 0)
            # pytest should have been invoked despite cache.
            self.assertEqual(len(runner.passthrough_calls), 1)


class TestNoChangesExitsCleanly(unittest.TestCase):
    def test_no_changes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_repo(root)

            runner = FakeRunner()
            out = io.StringIO()

            rc = run_cached_pytest(
                repo_root=root,
                runner=runner,
                out=out,
                err=io.StringIO(),
            )

            self.assertEqual(rc, 0)
            self.assertEqual(runner.passthrough_calls, [])
            self.assertIn("no python files", out.getvalue().lower())


class TestWatchModeIncludesUnstaged(unittest.TestCase):
    def test_watch_picks_up_unstaged(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_repo(root)

            runner = FakeRunner(
                git_diff_staged="",
                git_diff_unstaged="scripts_py/lib/foo.py\n",
                pytest_rc=0,
            )

            rc = run_cached_pytest(
                repo_root=root,
                runner=runner,
                watch_mode=True,
                out=io.StringIO(),
                err=io.StringIO(),
            )

            self.assertEqual(rc, 0)
            self.assertEqual(len(runner.passthrough_calls), 1)


class TestGlobalConfigChangeRunsAllTests(unittest.TestCase):
    def test_runs_all_tests_when_global_config_staged(self) -> None:
        """When a global config (devenv.nix) changes, ALL test files should run."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_repo(root)

            runner = FakeRunner(
                # No Python files changed, only global config.
                git_diff_staged="",
                git_diff_global_staged="devenv.nix\n",
                pytest_rc=0,
            )
            out, err = io.StringIO(), io.StringIO()

            rc = run_cached_pytest(
                repo_root=root,
                runner=runner,
                out=out,
                err=err,
            )

            self.assertEqual(rc, 0)
            # pytest should have been invoked.
            self.assertEqual(len(runner.passthrough_calls), 1)
            # Both test files should be in the args.
            cmd = runner.passthrough_calls[0]
            self.assertIn("test_foo", " ".join(cmd))
            self.assertIn("test_utils", " ".join(cmd))

    def test_invalidates_existing_attestations_on_global_change(self) -> None:
        """Existing attestations should be cleared when global config changes."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_repo(root)
            state_dir = root / ".devenv" / "state"

            # Pre-populate cache for test_foo.py.
            graph = build_import_graph(root)
            test_foo = root / "tests" / "test_foo.py"
            deps = transitive_deps(graph, test_foo)
            ch = compute_composite_hash(test_foo, deps, root)
            store_attestation(state_dir, test_foo, ch, ok=True, elapsed=0.5)

            runner = FakeRunner(
                git_diff_staged="",
                git_diff_global_staged="devenv.nix\n",
                pytest_rc=0,
            )
            out = io.StringIO()

            rc = run_cached_pytest(
                repo_root=root,
                runner=runner,
                out=out,
                err=io.StringIO(),
            )

            self.assertEqual(rc, 0)
            # Despite test_foo being previously cached, it should still run
            # because global config change invalidated all attestations.
            self.assertEqual(len(runner.passthrough_calls), 1)
            self.assertIn("invalidat", out.getvalue().lower())


if __name__ == "__main__":
    unittest.main()

"""Tests for scripts_py.lib.cached_check and scripts_py.cli.cached_check."""

from __future__ import annotations

import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from typing import Sequence

from scripts_py.cli.cached_check import run_cached_check
from scripts_py.lib.cached_check import (
    CHECKS_BY_NAME,
    CI_CHECKS,
    KNOWN_CHECKS,
    compute_input_hash,
    gc_stale,
    invalidate,
    lookup,
    lookup_named,
    store,
)


class FakeRunner:
    """Records calls and returns a configurable exit code."""

    def __init__(self, rc: int = 0) -> None:
        self.rc = rc
        self.calls: list[tuple[Sequence[str], str]] = []

    def run_passthrough(self, argv: Sequence[str], *, cwd: str) -> int:
        self.calls.append((tuple(argv), cwd))
        return self.rc


# ---------------------------------------------------------------------------
# Library tests
# ---------------------------------------------------------------------------


class TestComputeInputHash(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)

    def tearDown(self) -> None:
        self.td.cleanup()

    def test_hash_changes_when_file_changes(self) -> None:
        (self.root / "a.py").write_text("v1")
        h1 = compute_input_hash(self.root, files=("a.py",))

        (self.root / "a.py").write_text("v2")
        h2 = compute_input_hash(self.root, files=("a.py",))

        self.assertNotEqual(h1, h2)

    def test_hash_stable_for_same_content(self) -> None:
        (self.root / "a.py").write_text("hello")
        h1 = compute_input_hash(self.root, files=("a.py",))
        h2 = compute_input_hash(self.root, files=("a.py",))
        self.assertEqual(h1, h2)

    def test_globs_pick_up_files(self) -> None:
        src = self.root / "src"
        src.mkdir()
        (src / "a.py").write_text("a")
        (src / "b.py").write_text("b")

        h1 = compute_input_hash(self.root, globs=("src/**/*.py",))

        (src / "b.py").write_text("changed")
        h2 = compute_input_hash(self.root, globs=("src/**/*.py",))
        self.assertNotEqual(h1, h2)

    def test_excludes_devenv_dir(self) -> None:
        """Files under .devenv/ should not affect the hash."""
        devenv = self.root / ".devenv" / "state"
        devenv.mkdir(parents=True)
        (devenv / "foo.py").write_text("internal")
        (self.root / "a.py").write_text("code")

        h_with = compute_input_hash(self.root, globs=("**/*.py",))

        # Change the .devenv file — hash should not change.
        (devenv / "foo.py").write_text("changed")
        h_after = compute_input_hash(self.root, globs=("**/*.py",))
        self.assertEqual(h_with, h_after)

    def test_missing_file_gives_sentinel(self) -> None:
        """Explicit files that don't exist get a MISSING sentinel."""
        h = compute_input_hash(self.root, files=("nonexistent.toml",))
        self.assertTrue(len(h) == 64)  # Still a valid sha256 hex digest.


class TestStoreAndLookup(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.state = Path(self.td.name)

    def tearDown(self) -> None:
        self.td.cleanup()

    def test_store_and_lookup_pass(self) -> None:
        store(self.state, "ruff", "abc123", ok=True)
        self.assertIs(lookup(self.state, "ruff", "abc123"), True)

    def test_store_and_lookup_fail(self) -> None:
        store(self.state, "ruff", "abc123", ok=False)
        self.assertIs(lookup(self.state, "ruff", "abc123"), False)

    def test_lookup_miss(self) -> None:
        self.assertIsNone(lookup(self.state, "ruff", "missing"))

    def test_lookup_expired(self) -> None:
        store(self.state, "ruff", "abc123", ok=True)
        # Manually backdate the timestamp.
        d = self.state / "ruff-attestations"
        for p in d.glob("*.json"):
            data = json.loads(p.read_text())
            data["ts"] = time.time() - 200_000
            p.write_text(json.dumps(data))

        self.assertIsNone(lookup(self.state, "ruff", "abc123"))

    def test_different_name_no_collision(self) -> None:
        store(self.state, "ruff", "abc", ok=True)
        self.assertIsNone(lookup(self.state, "pyright", "abc"))

    def test_invalidate(self) -> None:
        store(self.state, "ruff", "a", ok=True)
        store(self.state, "ruff", "b", ok=True)
        n = invalidate(self.state, "ruff")
        self.assertEqual(n, 2)
        self.assertIsNone(lookup(self.state, "ruff", "a"))

    def test_gc_stale(self) -> None:
        store(self.state, "ruff", "old", ok=True)
        # Backdate it.
        d = self.state / "ruff-attestations"
        for p in d.glob("*.json"):
            data = json.loads(p.read_text())
            data["ts"] = time.time() - 200_000
            p.write_text(json.dumps(data))

        store(self.state, "ruff", "new", ok=True)

        n = gc_stale(self.state, "ruff")
        self.assertEqual(n, 1)
        # Fresh one still there.
        self.assertIs(lookup(self.state, "ruff", "new"), True)


class TestLookupNamed(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.state = self.root / ".devenv" / "state"
        # Create minimal files for the ruff check.
        (self.root / "scripts_py").mkdir()
        (self.root / "scripts_py" / "__init__.py").write_text("")
        (self.root / "tests").mkdir()
        (self.root / "tests" / "__init__.py").write_text("")
        (self.root / "pyproject.toml").write_text("")

    def tearDown(self) -> None:
        self.td.cleanup()

    def test_unknown_name_returns_none(self) -> None:
        self.assertIsNone(lookup_named(self.state, self.root, "nonexistent"))

    def test_round_trip_named(self) -> None:
        check = CHECKS_BY_NAME["ruff"]
        h = compute_input_hash(self.root, globs=check.globs, files=check.files)
        store(self.state, "ruff", h, ok=True)
        self.assertIs(lookup_named(self.state, self.root, "ruff"), True)


class TestCheckRegistry(unittest.TestCase):
    def test_no_duplicate_names(self) -> None:
        names = [c.name for c in KNOWN_CHECKS]
        self.assertEqual(len(names), len(set(names)))

    def test_checks_by_name_consistent(self) -> None:
        for c in KNOWN_CHECKS:
            self.assertIn(c.name, CHECKS_BY_NAME)
            self.assertEqual(CHECKS_BY_NAME[c.name], c)

    def test_ci_checks_subset_of_known(self) -> None:
        self.assertTrue(len(CI_CHECKS) > 0)
        self.assertTrue(len(CI_CHECKS) < len(KNOWN_CHECKS))
        ci_names = {c.name for c in CI_CHECKS}
        all_names = {c.name for c in KNOWN_CHECKS}
        self.assertTrue(ci_names.issubset(all_names))
        # All CI checks have ci_check=True.
        for c in CI_CHECKS:
            self.assertTrue(c.ci_check)
        # Formatter checks are excluded.
        fmt_names = all_names - ci_names
        self.assertTrue(len(fmt_names) > 0)
        for name in fmt_names:
            self.assertFalse(CHECKS_BY_NAME[name].ci_check)


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestRunCachedCheck(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "a.py").write_text("# code")
        (self.root / "pyproject.toml").write_text("[tool.ruff]")
        (self.root / "scripts_py").mkdir()
        (self.root / "scripts_py" / "__init__.py").write_text("")

    def tearDown(self) -> None:
        self.td.cleanup()

    def test_runs_command_when_no_cache(self) -> None:
        runner = FakeRunner(rc=0)
        out = io.StringIO()
        rc = run_cached_check(
            name="ruff",
            globs=("src/**/*.py",),
            files=("pyproject.toml",),
            command=["ruff", "check", "src"],
            repo_root=self.root,
            runner=runner,
            out=out,
        )
        self.assertEqual(rc, 0)
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(runner.calls[0][0], ("ruff", "check", "src"))

    def test_skips_when_cached_pass(self) -> None:
        # Pre-populate the cache.
        state = self.root / ".devenv" / "state"
        h = compute_input_hash(self.root, globs=("src/**/*.py",), files=("pyproject.toml",))
        store(state, "ruff", h, ok=True)

        runner = FakeRunner(rc=0)
        out = io.StringIO()
        rc = run_cached_check(
            name="ruff",
            globs=("src/**/*.py",),
            files=("pyproject.toml",),
            command=["ruff", "check"],
            repo_root=self.root,
            runner=runner,
            out=out,
        )
        self.assertEqual(rc, 0)
        self.assertEqual(len(runner.calls), 0)
        self.assertIn("skipping", out.getvalue().lower())

    def test_reruns_after_file_change(self) -> None:
        state = self.root / ".devenv" / "state"
        h = compute_input_hash(self.root, globs=("src/**/*.py",), files=("pyproject.toml",))
        store(state, "ruff", h, ok=True)

        # Modify source.
        (self.root / "src" / "a.py").write_text("# changed")

        runner = FakeRunner(rc=0)
        out = io.StringIO()
        rc = run_cached_check(
            name="ruff",
            globs=("src/**/*.py",),
            files=("pyproject.toml",),
            command=["ruff", "check"],
            repo_root=self.root,
            runner=runner,
            out=out,
        )
        self.assertEqual(rc, 0)
        self.assertEqual(len(runner.calls), 1)

    def test_force_ignores_cache(self) -> None:
        state = self.root / ".devenv" / "state"
        h = compute_input_hash(self.root, globs=("src/**/*.py",), files=("pyproject.toml",))
        store(state, "ruff", h, ok=True)

        runner = FakeRunner(rc=0)
        out = io.StringIO()
        rc = run_cached_check(
            name="ruff",
            globs=("src/**/*.py",),
            files=("pyproject.toml",),
            command=["ruff", "check"],
            repo_root=self.root,
            runner=runner,
            force=True,
            out=out,
        )
        self.assertEqual(rc, 0)
        self.assertEqual(len(runner.calls), 1)

    def test_propagates_nonzero_exit(self) -> None:
        runner = FakeRunner(rc=1)
        err = io.StringIO()
        rc = run_cached_check(
            name="ruff",
            globs=("src/**/*.py",),
            files=(),
            command=["ruff", "check"],
            repo_root=self.root,
            runner=runner,
            err=err,
        )
        self.assertEqual(rc, 1)
        self.assertIn("FAILED", err.getvalue())

    def test_stores_attestation_after_pass(self) -> None:
        runner = FakeRunner(rc=0)
        run_cached_check(
            name="ruff",
            globs=("src/**/*.py",),
            files=(),
            command=["ruff", "check"],
            repo_root=self.root,
            runner=runner,
        )

        # Second run should skip.
        runner2 = FakeRunner(rc=0)
        out = io.StringIO()
        rc = run_cached_check(
            name="ruff",
            globs=("src/**/*.py",),
            files=(),
            command=["ruff", "check"],
            repo_root=self.root,
            runner=runner2,
            out=out,
        )
        self.assertEqual(rc, 0)
        self.assertEqual(len(runner2.calls), 0)

    def test_fail_attestation_causes_rerun(self) -> None:
        state = self.root / ".devenv" / "state"
        h = compute_input_hash(self.root, globs=("src/**/*.py",), files=())
        store(state, "ruff", h, ok=False)

        runner = FakeRunner(rc=0)
        err = io.StringIO()
        rc = run_cached_check(
            name="ruff",
            globs=("src/**/*.py",),
            files=(),
            command=["ruff", "check"],
            repo_root=self.root,
            runner=runner,
            err=err,
        )
        self.assertEqual(rc, 0)
        self.assertEqual(len(runner.calls), 1)


if __name__ == "__main__":
    unittest.main()

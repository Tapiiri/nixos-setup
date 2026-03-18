"""Tests for scripts_py.cli.cached_nix_check."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from typing import Sequence

from scripts_py.cli.cached_nix_check import run_cached_nix_check
from scripts_py.lib.nix_check_attestation import (
    compute_nix_hash,
    store_nix_attestation,
)


class FakeRunner:
    """Records calls and returns a configurable exit code."""

    def __init__(self, rc: int = 0) -> None:
        self.rc = rc
        self.calls: list[tuple[Sequence[str], str]] = []

    def run_passthrough(self, argv: Sequence[str], *, cwd: str) -> int:
        self.calls.append((tuple(argv), cwd))
        return self.rc


class TestCachedNixCheck(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        # Minimal nix layout.
        (self.root / "flake.nix").write_text("{ }")
        (self.root / "flake.lock").write_text("{}")
        (self.root / "devenv.nix").write_text("{pkgs}: {}")
        # Marker files so repo_root detection would work (not used directly).
        (self.root / "scripts_py").mkdir()
        (self.root / "scripts_py" / "__init__.py").write_text("")

    def tearDown(self) -> None:
        self.td.cleanup()

    def test_runs_check_when_no_cache(self) -> None:
        runner = FakeRunner(rc=0)
        out = io.StringIO()
        rc = run_cached_nix_check(repo_root=self.root, runner=runner, out=out)
        self.assertEqual(rc, 0)
        self.assertEqual(len(runner.calls), 1)
        self.assertIn("nix", runner.calls[0][0])

    def test_skips_when_cached_pass(self) -> None:
        """Pre-store a passing attestation → check should be skipped."""
        state = self.root / ".devenv" / "state"
        nix_hash = compute_nix_hash(self.root)
        store_nix_attestation(state, nix_hash, ok=True)

        runner = FakeRunner(rc=0)
        out = io.StringIO()
        rc = run_cached_nix_check(repo_root=self.root, runner=runner, out=out)
        self.assertEqual(rc, 0)
        # No subprocess calls — skipped.
        self.assertEqual(len(runner.calls), 0)
        self.assertIn("skipping", out.getvalue().lower())

    def test_reruns_after_file_change(self) -> None:
        """A passing attestation should not apply after a .nix file changes."""
        state = self.root / ".devenv" / "state"
        nix_hash = compute_nix_hash(self.root)
        store_nix_attestation(state, nix_hash, ok=True)

        # Modify a .nix file.
        (self.root / "flake.nix").write_text("{ outputs = {}; }")

        runner = FakeRunner(rc=0)
        out = io.StringIO()
        rc = run_cached_nix_check(repo_root=self.root, runner=runner, out=out)
        self.assertEqual(rc, 0)
        # Should have actually run the check.
        self.assertEqual(len(runner.calls), 1)

    def test_force_ignores_cache(self) -> None:
        state = self.root / ".devenv" / "state"
        nix_hash = compute_nix_hash(self.root)
        store_nix_attestation(state, nix_hash, ok=True)

        runner = FakeRunner(rc=0)
        out = io.StringIO()
        rc = run_cached_nix_check(repo_root=self.root, runner=runner, force=True, out=out)
        self.assertEqual(rc, 0)
        # Forced — should run despite cache hit.
        self.assertEqual(len(runner.calls), 1)

    def test_propagates_nonzero_exit(self) -> None:
        runner = FakeRunner(rc=1)
        err = io.StringIO()
        rc = run_cached_nix_check(repo_root=self.root, runner=runner, err=err)
        self.assertEqual(rc, 1)
        self.assertIn("FAILED", err.getvalue())

    def test_stores_attestation_after_pass(self) -> None:
        runner = FakeRunner(rc=0)
        run_cached_nix_check(repo_root=self.root, runner=runner)

        # Second run should skip.
        runner2 = FakeRunner(rc=0)
        out = io.StringIO()
        rc = run_cached_nix_check(repo_root=self.root, runner=runner2, out=out)
        self.assertEqual(rc, 0)
        self.assertEqual(len(runner2.calls), 0)

    def test_fail_attestation_causes_rerun(self) -> None:
        """A failing attestation should still cause a re-run."""
        state = self.root / ".devenv" / "state"
        nix_hash = compute_nix_hash(self.root)
        store_nix_attestation(state, nix_hash, ok=False)

        runner = FakeRunner(rc=0)
        err = io.StringIO()
        rc = run_cached_nix_check(repo_root=self.root, runner=runner, err=err)
        self.assertEqual(rc, 0)
        self.assertEqual(len(runner.calls), 1)


class TestMainCLI(unittest.TestCase):
    """Smoke tests for the CLI entry point."""

    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        (self.root / "flake.nix").write_text("{ }")
        (self.root / "flake.lock").write_text("{}")
        (self.root / "scripts_py").mkdir()
        (self.root / "scripts_py" / "__init__.py").write_text("")

    def tearDown(self) -> None:
        self.td.cleanup()

    def test_gc_flag(self) -> None:
        # Pre-store something.
        state = self.root / ".devenv" / "state"
        store_nix_attestation(state, "abc", ok=True)

        # Patch repo_root to use temp dir — gc should work via main()
        # (this is tricky since main uses __file__; just test the library fn)
        from scripts_py.lib.nix_check_attestation import gc_nix_stale

        n = gc_nix_stale(state)
        self.assertEqual(n, 0)  # Fresh, so not removed.


if __name__ == "__main__":
    unittest.main()

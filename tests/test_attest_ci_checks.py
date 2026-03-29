"""Tests for scripts_py.ci.attest_ci_checks — especially --verify-local."""

from __future__ import annotations

import io
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any, Sequence

from scripts_py.ci.attest_ci_checks import (
    Options,
    SimpleCompletedProcess,
    attest_ci_checks,
    parse_args,
    verify_local_attestations,
)
from scripts_py.lib.cached_check import (
    CI_CHECKS,
    compute_input_hash,
)
from scripts_py.lib.cached_check import (
    store as store_check_attestation,
)

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_repo(root: Path) -> None:
    """Create a minimal repo tree that satisfies hash computation + import graph."""
    (root / "flake.nix").write_text("{ }")
    (root / "flake.lock").write_text("{}")
    (root / "devenv.nix").write_text("{pkgs}: {}")
    (root / "pyproject.toml").write_text("[tool.pytest]")
    scripts_py = root / "scripts_py"
    scripts_py.mkdir(parents=True, exist_ok=True)
    (scripts_py / "__init__.py").write_text("")
    tests = root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "__init__.py").write_text("")
    (tests / "conftest.py").write_text("")
    (tests / "test_alpha.py").write_text(
        "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self): pass\n"
    )
    (tests / "test_beta.py").write_text(
        "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self): pass\n"
    )


def _store_all_attestations(root: Path) -> None:
    """Write passing attestation for every CI_CHECKS entry."""
    _store_fresh_check_attestations(root)


def _store_fresh_check_attestations(
    root: Path, *, exclude: set[str] | None = None
) -> None:
    """Write passing attestation for every CI_CHECKS entry."""
    state = root / ".devenv" / "state"
    skip = exclude or set()
    for check in CI_CHECKS:
        if check.name in skip:
            continue
        h = compute_input_hash(root, globs=check.globs, files=check.files)
        store_check_attestation(state, check.name, h, ok=True)


# ------------------------------------------------------------------
# Tests: verify_local_attestations
# ------------------------------------------------------------------


class TestVerifyLocalAttestations(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        _make_repo(self.root)

    def tearDown(self) -> None:
        self.td.cleanup()

    def test_returns_true_when_all_fresh(self) -> None:
        _store_all_attestations(self.root)
        out, err = io.StringIO(), io.StringIO()
        self.assertTrue(verify_local_attestations(self.root, out=out, err=err))
        self.assertIn("verified", out.getvalue().lower())

    def test_returns_false_when_nix_missing(self) -> None:
        # Store all check attestations except nix-flake-check.
        _store_fresh_check_attestations(self.root, exclude={"nix-flake-check"})
        err = io.StringIO()
        self.assertFalse(verify_local_attestations(self.root, err=err))
        self.assertIn("nix-flake-check", err.getvalue())

    def test_returns_false_when_tests_missing(self) -> None:
        # Store all check attestations except pytest.
        _store_fresh_check_attestations(self.root, exclude={"pytest"})
        err = io.StringIO()
        self.assertFalse(verify_local_attestations(self.root, err=err))
        self.assertIn("not attested", err.getvalue().lower())

    def test_accepts_old_nix_attestation_with_matching_hash(self) -> None:
        """Old attestations are valid as long as the content hash matches."""
        _store_all_attestations(self.root)
        # Backdate nix-flake-check attestation to 2 hours ago.
        import json

        state = self.root / ".devenv" / "state"
        nix_dir = state / "nix-flake-check-attestations"
        for p in nix_dir.glob("*.json"):
            data = json.loads(p.read_text())
            data["ts"] = time.time() - 7200
            p.write_text(json.dumps(data))

        out, err = io.StringIO(), io.StringIO()
        self.assertTrue(verify_local_attestations(self.root, out=out, err=err))

    def test_accepts_old_test_attestation_with_matching_hash(self) -> None:
        """Old test attestations are valid as long as the content hash matches."""
        _store_all_attestations(self.root)
        import json

        state = self.root / ".devenv" / "state"
        test_dir = state / "pytest-attestations"
        for p in test_dir.glob("*.json"):
            data = json.loads(p.read_text())
            data["ts"] = time.time() - 7200
            p.write_text(json.dumps(data))

        out, err = io.StringIO(), io.StringIO()
        self.assertTrue(verify_local_attestations(self.root, out=out, err=err))

    def test_returns_false_when_nix_file_changed(self) -> None:
        """If a nix file changed after the attestation, hash won't match."""
        _store_all_attestations(self.root)
        # Modify a nix file after attestation.
        (self.root / "flake.nix").write_text("{ outputs = {}; }")
        err = io.StringIO()
        self.assertFalse(verify_local_attestations(self.root, err=err))

    def test_returns_false_when_test_file_changed(self) -> None:
        """If a test file changed, the pytest attestation hash won't match."""
        _store_all_attestations(self.root)
        (self.root / "tests" / "test_alpha.py").write_text("# changed\n")
        err = io.StringIO()
        self.assertFalse(verify_local_attestations(self.root, err=err))

    def test_returns_false_when_no_test_files(self) -> None:
        """Repo with no test_*.py files should still pass if pytest attestation matches."""
        # Remove all test files first, then store check attestations
        # (ruff/pyright/pytest globs include tests/**/*.py, so hash changes).
        for f in (self.root / "tests").glob("test_*.py"):
            f.unlink()
        _store_all_attestations(self.root)
        out, err = io.StringIO(), io.StringIO()
        self.assertTrue(verify_local_attestations(self.root, out=out, err=err))

    def test_returns_false_when_nix_attestation_marked_failed(self) -> None:
        """A nix attestation with ok=False should fail verification."""
        state = self.root / ".devenv" / "state"
        h = compute_input_hash(self.root, globs=("**/*.nix",), files=("flake.lock",))
        store_check_attestation(state, "nix-flake-check", h, ok=False)
        # Store everything else as passing (but not nix-flake-check, to keep the failed one).
        _store_fresh_check_attestations(self.root, exclude={"nix-flake-check"})
        err = io.StringIO()
        self.assertFalse(verify_local_attestations(self.root, err=err))


# ------------------------------------------------------------------
# Tests: parse_args
# ------------------------------------------------------------------


class TestParseArgs(unittest.TestCase):
    def test_verify_local_flag(self) -> None:
        opts = parse_args(["--verify-local", "--no-run"])
        self.assertTrue(opts.verify_local)
        self.assertFalse(opts.run_task)

    def test_default_no_verify_local(self) -> None:
        opts = parse_args([])
        self.assertFalse(opts.verify_local)


# ------------------------------------------------------------------
# Tests: attest_ci_checks with --verify-local
# ------------------------------------------------------------------


class FakeRunner:
    """Records calls and returns configurable results."""

    def __init__(self, rev_parse_sha: str = "abc123def456") -> None:
        self.rev_parse_sha = rev_parse_sha
        self.calls: list[list[str]] = []

    def run_capture(self, argv: Sequence[str]) -> SimpleCompletedProcess:
        self.calls.append(list(argv))

        if argv[:2] == ["git", "rev-parse"]:
            return SimpleCompletedProcess(returncode=0, stdout=self.rev_parse_sha, stderr="")
        elif argv[:2] == ["devenv", "version"]:
            return SimpleCompletedProcess(returncode=0, stdout="1.0.0", stderr="")
        else:
            return SimpleCompletedProcess(returncode=1, stdout="", stderr="unexpected")

    def run_check(self, argv: Sequence[str]) -> None:
        self.calls.append(list(argv))


class TestAttestCiChecksVerifyLocal(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        _make_repo(self.root)

    def tearDown(self) -> None:
        self.td.cleanup()

    def test_skips_note_when_verify_local_fails(self) -> None:
        """With --verify-local and no caches, no git note should be written."""
        runner = FakeRunner()
        out, err = io.StringIO(), io.StringIO()
        opts = Options(
            task="check:all",
            notes_ref="refs/notes/test",
            remote="origin",
            push=False,
            strict_push=False,
            commit="HEAD",
            run_task=False,
            verify_local=True,
        )
        # Monkey-patch repo_root resolution for the test.
        import scripts_py.ci.attest_ci_checks as mod

        original = mod.repo_root_from_script_path

        def _fake_root(_p: Any, **kw: Any) -> Path:
            return self.root

        mod.repo_root_from_script_path = _fake_root  # type: ignore[assignment]
        try:
            wrote = attest_ci_checks(opts=opts, runner=runner, out=out, err=err)
        finally:
            mod.repo_root_from_script_path = original

        self.assertFalse(wrote)
        # No git notes commands should have been issued.
        note_cmds = [c for c in runner.calls if c[:2] == ["git", "notes"]]
        self.assertEqual(note_cmds, [])

    def test_writes_note_when_verify_local_passes(self) -> None:
        """With --verify-local and fresh caches, note should be written."""
        _store_all_attestations(self.root)

        runner = FakeRunner()
        out, err = io.StringIO(), io.StringIO()
        opts = Options(
            task="check:all",
            notes_ref="refs/notes/test",
            remote="origin",
            push=False,
            strict_push=False,
            commit="HEAD",
            run_task=False,
            verify_local=True,
        )
        import scripts_py.ci.attest_ci_checks as mod

        original = mod.repo_root_from_script_path

        def _fake_root(_p: Any, **kw: Any) -> Path:
            return self.root

        mod.repo_root_from_script_path = _fake_root  # type: ignore[assignment]
        try:
            wrote = attest_ci_checks(opts=opts, runner=runner, out=out, err=err)
        finally:
            mod.repo_root_from_script_path = original

        self.assertTrue(wrote)
        note_cmds = [c for c in runner.calls if c[:2] == ["git", "notes"]]
        self.assertEqual(len(note_cmds), 1)

    def test_writes_note_without_verify_local(self) -> None:
        """Without --verify-local, note should always be written."""
        runner = FakeRunner()
        out, err = io.StringIO(), io.StringIO()
        opts = Options(
            task="check:all",
            notes_ref="refs/notes/test",
            remote="origin",
            push=False,
            strict_push=False,
            commit="HEAD",
            run_task=False,
            verify_local=False,
        )
        import scripts_py.ci.attest_ci_checks as mod

        original = mod.repo_root_from_script_path

        def _fake_root(_p: Any, **kw: Any) -> Path:
            return self.root

        mod.repo_root_from_script_path = _fake_root  # type: ignore[assignment]
        try:
            wrote = attest_ci_checks(opts=opts, runner=runner, out=out, err=err)
        finally:
            mod.repo_root_from_script_path = original

        self.assertTrue(wrote)
        note_cmds = [c for c in runner.calls if c[:2] == ["git", "notes"]]
        self.assertEqual(len(note_cmds), 1)

    def test_auto_recovery_runs_task_and_reseeds_caches(self) -> None:
        """With --verify-local and run_task=True, stale caches trigger check:all then re-verify."""
        import scripts_py.ci.attest_ci_checks as mod

        original = mod.repo_root_from_script_path
        root = self.root

        def _fake_root(_p: Any, **kw: Any) -> Path:
            return root

        # Track how many times run_check is called and seed caches on the
        # "devenv tasks run" call to simulate the task re-seeding caches.
        class SeedingRunner(FakeRunner):
            def run_check(self, argv: Sequence[str]) -> None:
                super().run_check(argv)
                if argv[:3] == ["devenv", "tasks", "run"]:
                    # Simulate check:all seeding all caches.
                    _store_all_attestations(root)

        runner = SeedingRunner()
        out, err = io.StringIO(), io.StringIO()
        opts = Options(
            task="check:all",
            notes_ref="refs/notes/test",
            remote="origin",
            push=False,
            strict_push=False,
            commit="HEAD",
            run_task=True,
            verify_local=True,
        )

        mod.repo_root_from_script_path = _fake_root  # type: ignore[assignment]
        try:
            wrote = attest_ci_checks(opts=opts, runner=runner, out=out, err=err)
        finally:
            mod.repo_root_from_script_path = original

        # Should have written a note after auto-recovery.
        self.assertTrue(wrote)
        # Should have called devenv tasks run to re-seed.
        task_cmds = [c for c in runner.calls if "devenv" in c and "tasks" in c]
        self.assertEqual(len(task_cmds), 1)
        note_cmds = [c for c in runner.calls if c[:2] == ["git", "notes"]]
        self.assertEqual(len(note_cmds), 1)
        self.assertIn("stale", out.getvalue().lower())

    def test_auto_recovery_still_fails_if_task_doesnt_fix_caches(self) -> None:
        """If check:all runs but caches remain stale, no note is written."""
        import scripts_py.ci.attest_ci_checks as mod

        original = mod.repo_root_from_script_path

        def _fake_root(_p: Any, **kw: Any) -> Path:
            return self.root

        # run_check does nothing — caches stay stale.
        runner = FakeRunner()
        out, err = io.StringIO(), io.StringIO()
        opts = Options(
            task="check:all",
            notes_ref="refs/notes/test",
            remote="origin",
            push=False,
            strict_push=False,
            commit="HEAD",
            run_task=True,
            verify_local=True,
        )

        mod.repo_root_from_script_path = _fake_root  # type: ignore[assignment]
        try:
            wrote = attest_ci_checks(opts=opts, runner=runner, out=out, err=err)
        finally:
            mod.repo_root_from_script_path = original

        self.assertFalse(wrote)
        # Should have attempted devenv tasks run.
        task_cmds = [c for c in runner.calls if "devenv" in c and "tasks" in c]
        self.assertEqual(len(task_cmds), 1)
        # No note should have been written.
        note_cmds = [c for c in runner.calls if c[:2] == ["git", "notes"]]
        self.assertEqual(note_cmds, [])


if __name__ == "__main__":
    unittest.main()

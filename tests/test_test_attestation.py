"""Tests for scripts_py.lib.test_attestation — file-level test result caching."""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from scripts_py.lib.test_attestation import (
    CACHE_DIR_NAME,
    compute_composite_hash,
    gc_stale,
    invalidate_all,
    lookup_attestation,
    store_attestation,
)


class TestCompositeHash(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        # Create minimal files referenced by the hash.
        (self.root / "pyproject.toml").write_text("[tool.pytest]")
        (self.root / "devenv.nix").write_text("{}")
        (self.root / "test_a.py").write_text("import unittest")
        (self.root / "dep.py").write_text("# dep")

    def tearDown(self) -> None:
        self.td.cleanup()

    def test_deterministic(self) -> None:
        """Same inputs always produce the same hash."""
        h1 = compute_composite_hash(self.root / "test_a.py", {self.root / "dep.py"}, self.root)
        h2 = compute_composite_hash(self.root / "test_a.py", {self.root / "dep.py"}, self.root)
        self.assertEqual(h1, h2)

    def test_changes_on_dep_change(self) -> None:
        h1 = compute_composite_hash(self.root / "test_a.py", {self.root / "dep.py"}, self.root)
        (self.root / "dep.py").write_text("# changed dep")
        h2 = compute_composite_hash(self.root / "test_a.py", {self.root / "dep.py"}, self.root)
        self.assertNotEqual(h1, h2)

    def test_changes_on_test_file_change(self) -> None:
        h1 = compute_composite_hash(self.root / "test_a.py", {self.root / "dep.py"}, self.root)
        (self.root / "test_a.py").write_text("import unittest  # new")
        h2 = compute_composite_hash(self.root / "test_a.py", {self.root / "dep.py"}, self.root)
        self.assertNotEqual(h1, h2)

    def test_changes_on_global_config_change(self) -> None:
        h1 = compute_composite_hash(self.root / "test_a.py", {self.root / "dep.py"}, self.root)
        (self.root / "pyproject.toml").write_text("[tool.pytest]\naddopts = '-v'")
        h2 = compute_composite_hash(self.root / "test_a.py", {self.root / "dep.py"}, self.root)
        self.assertNotEqual(h1, h2)

    def test_missing_dep_uses_sentinel(self) -> None:
        """A nonexistent dep file produces a stable 'MISSING' sentinel."""
        h = compute_composite_hash(
            self.root / "test_a.py",
            {self.root / "no_such_file.py"},
            self.root,
        )
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)  # hex sha256


class TestStoreAndLookup(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.td.name)
        self.test_file = Path("/repo/tests/test_a.py")

    def tearDown(self) -> None:
        self.td.cleanup()

    def test_round_trip_pass(self) -> None:
        store_attestation(self.state_dir, self.test_file, "abc123", ok=True, elapsed=1.5)
        result = lookup_attestation(self.state_dir, self.test_file, "abc123")
        self.assertTrue(result)

    def test_round_trip_fail(self) -> None:
        store_attestation(self.state_dir, self.test_file, "abc123", ok=False, elapsed=0.5)
        result = lookup_attestation(self.state_dir, self.test_file, "abc123")
        self.assertFalse(result)

    def test_missing_returns_none(self) -> None:
        result = lookup_attestation(self.state_dir, self.test_file, "nonexistent")
        self.assertIsNone(result)

    def test_wrong_hash_returns_none(self) -> None:
        store_attestation(self.state_dir, self.test_file, "abc123", ok=True)
        result = lookup_attestation(self.state_dir, self.test_file, "def456")
        self.assertIsNone(result)

    def test_expired_returns_none(self) -> None:
        p = store_attestation(self.state_dir, self.test_file, "abc123", ok=True)
        # Backdate the timestamp.
        data = json.loads(p.read_text(encoding="utf-8"))
        data["ts"] = time.time() - 200_000
        p.write_text(json.dumps(data), encoding="utf-8")
        result = lookup_attestation(self.state_dir, self.test_file, "abc123", max_age_s=86400)
        self.assertIsNone(result)


class TestInvalidateAll(unittest.TestCase):
    def test_removes_all_entries(self) -> None:
        td = tempfile.TemporaryDirectory()
        state_dir = Path(td.name)
        tf = Path("/repo/tests/test_a.py")

        store_attestation(state_dir, tf, "h1", ok=True)
        store_attestation(state_dir, tf, "h2", ok=False)

        n = invalidate_all(state_dir)
        self.assertEqual(n, 2)

        # Cache dir should be empty now.
        remaining = list((state_dir / CACHE_DIR_NAME).glob("*.json"))
        self.assertEqual(remaining, [])
        td.cleanup()


class TestGcStale(unittest.TestCase):
    def test_removes_old_keeps_new(self) -> None:
        td = tempfile.TemporaryDirectory()
        state_dir = Path(td.name)
        tf = Path("/repo/tests/test_a.py")

        # Store two attestations.
        p_old = store_attestation(state_dir, tf, "old_hash", ok=True)
        store_attestation(state_dir, tf, "new_hash", ok=True)

        # Backdate the first one.
        data = json.loads(p_old.read_text(encoding="utf-8"))
        data["ts"] = time.time() - 200_000
        p_old.write_text(json.dumps(data), encoding="utf-8")

        n = gc_stale(state_dir, max_age_s=86400)
        self.assertEqual(n, 1)

        # Only the new one should remain.
        remaining = list((state_dir / CACHE_DIR_NAME).glob("*.json"))
        self.assertEqual(len(remaining), 1)
        td.cleanup()


if __name__ == "__main__":
    unittest.main()

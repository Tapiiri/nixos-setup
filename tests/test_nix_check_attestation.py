# pyright: reportPrivateUsage=false
"""Tests for scripts_py.lib.nix_check_attestation."""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from scripts_py.lib.nix_check_attestation import (
    _EXCLUDED_DIRS,
    _EXTRA_FILES,
    compute_nix_hash,
    gc_nix_stale,
    invalidate_nix_attestations,
    lookup_nix_attestation,
    store_nix_attestation,
)


class TestComputeNixHash(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        # Minimal .nix layout
        (self.root / "flake.nix").write_text("{ }")
        (self.root / "flake.lock").write_text("{}")
        (self.root / "devenv.nix").write_text("{pkgs}: {}")
        sub = self.root / "home" / "modules"
        sub.mkdir(parents=True)
        (sub / "core.nix").write_text("{ }")

    def tearDown(self) -> None:
        self.td.cleanup()

    def test_deterministic(self) -> None:
        h1 = compute_nix_hash(self.root)
        h2 = compute_nix_hash(self.root)
        self.assertEqual(h1, h2)

    def test_changes_on_file_edit(self) -> None:
        h1 = compute_nix_hash(self.root)
        (self.root / "flake.nix").write_text("{ outputs = {}; }")
        h2 = compute_nix_hash(self.root)
        self.assertNotEqual(h1, h2)

    def test_changes_on_lock_edit(self) -> None:
        h1 = compute_nix_hash(self.root)
        (self.root / "flake.lock").write_text('{"nodes":{}}')
        h2 = compute_nix_hash(self.root)
        self.assertNotEqual(h1, h2)

    def test_excludes_devenv_dir(self) -> None:
        """Files under .devenv/ should not affect the hash."""
        h1 = compute_nix_hash(self.root)
        devenv = self.root / ".devenv"
        devenv.mkdir()
        (devenv / "internal.nix").write_text("# should be ignored")
        h2 = compute_nix_hash(self.root)
        self.assertEqual(h1, h2)

    def test_excludes_result_dir(self) -> None:
        """Files under result/ should not affect the hash."""
        h1 = compute_nix_hash(self.root)
        res = self.root / "result"
        res.mkdir()
        (res / "internal.nix").write_text("# should be ignored")
        h2 = compute_nix_hash(self.root)
        self.assertEqual(h1, h2)

    def test_new_nix_file_changes_hash(self) -> None:
        h1 = compute_nix_hash(self.root)
        (self.root / "extra.nix").write_text("{ }")
        h2 = compute_nix_hash(self.root)
        self.assertNotEqual(h1, h2)

    def test_extra_files_tuple(self) -> None:
        """flake.lock should be in _EXTRA_FILES."""
        self.assertIn("flake.lock", _EXTRA_FILES)

    def test_excluded_dirs_set(self) -> None:
        self.assertIn(".devenv", _EXCLUDED_DIRS)
        self.assertIn("result", _EXCLUDED_DIRS)


class TestStoreAndLookup(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.state = Path(self.td.name)

    def tearDown(self) -> None:
        self.td.cleanup()

    def test_store_and_lookup_pass(self) -> None:
        h = "abc123"
        store_nix_attestation(self.state, h, ok=True, elapsed=1.5)
        self.assertIs(lookup_nix_attestation(self.state, h), True)

    def test_store_and_lookup_fail(self) -> None:
        h = "abc123"
        store_nix_attestation(self.state, h, ok=False, elapsed=0.7)
        self.assertIs(lookup_nix_attestation(self.state, h), False)

    def test_lookup_miss(self) -> None:
        self.assertIsNone(lookup_nix_attestation(self.state, "nonexistent"))

    def test_lookup_expired(self) -> None:
        h = "abc123"
        p = store_nix_attestation(self.state, h, ok=True)
        # Backdate the record.
        data = json.loads(p.read_text())
        data["ts"] = time.time() - 100_000
        p.write_text(json.dumps(data))
        self.assertIsNone(lookup_nix_attestation(self.state, h))


class TestInvalidateAndGC(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.state = Path(self.td.name)

    def tearDown(self) -> None:
        self.td.cleanup()

    def test_invalidate_all(self) -> None:
        store_nix_attestation(self.state, "h1", ok=True)
        store_nix_attestation(self.state, "h2", ok=True)
        n = invalidate_nix_attestations(self.state)
        self.assertEqual(n, 2)
        self.assertIsNone(lookup_nix_attestation(self.state, "h1"))
        self.assertIsNone(lookup_nix_attestation(self.state, "h2"))

    def test_gc_only_removes_stale(self) -> None:
        store_nix_attestation(self.state, "fresh", ok=True)
        p = store_nix_attestation(self.state, "old", ok=True)
        # Backdate one.
        data = json.loads(p.read_text())
        data["ts"] = time.time() - 100_000
        p.write_text(json.dumps(data))
        n = gc_nix_stale(self.state)
        self.assertEqual(n, 1)
        # Fresh one survives.
        self.assertIs(lookup_nix_attestation(self.state, "fresh"), True)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts_py.cli.remote_flake_inputs import get_remote_input_names, main

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

LOCK_MIXED: dict[str, Any] = {
    "nodes": {
        "nixpkgs": {"locked": {}, "original": {"type": "github"}},
        "home-manager": {"locked": {}, "original": {"type": "github"}},
        "my-local": {"locked": {}, "original": {"type": "path"}},
        "root": {
            "inputs": {
                "nixpkgs": "nixpkgs",
                "home-manager": "home-manager",
                "my-local": "my-local",
            }
        },
    },
    "root": "root",
    "version": 7,
}

LOCK_ALL_REMOTE: dict[str, Any] = {
    "nodes": {
        "nixpkgs": {"locked": {}, "original": {"type": "github"}},
        "disko": {"locked": {}, "original": {"type": "github"}},
        "root": {
            "inputs": {
                "nixpkgs": "nixpkgs",
                "disko": "disko",
            }
        },
    },
    "root": "root",
    "version": 7,
}

LOCK_ALL_LOCAL: dict[str, Any] = {
    "nodes": {
        "local-a": {"locked": {}, "original": {"type": "path"}},
        "local-b": {"locked": {}, "original": {"type": "path"}},
        "root": {
            "inputs": {
                "local-a": "local-a",
                "local-b": "local-b",
            }
        },
    },
    "root": "root",
    "version": 7,
}

LOCK_NO_TYPE: dict[str, Any] = {
    "nodes": {
        "mystery": {"locked": {}, "original": {}},
        "root": {
            "inputs": {
                "mystery": "mystery",
            }
        },
    },
    "root": "root",
    "version": 7,
}


def _write_lock(tmp: Path, data: dict[str, Any]) -> Path:
    lock = tmp / "flake.lock"
    lock.write_text(json.dumps(data), encoding="utf-8")
    return lock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetRemoteInputNames(unittest.TestCase):
    def test_filters_path_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            lock = _write_lock(Path(d), LOCK_MIXED)
            result = get_remote_input_names(lock)
        self.assertEqual(result, ["home-manager", "nixpkgs"])

    def test_all_remote(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            lock = _write_lock(Path(d), LOCK_ALL_REMOTE)
            result = get_remote_input_names(lock)
        self.assertEqual(result, ["disko", "nixpkgs"])

    def test_all_local(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            lock = _write_lock(Path(d), LOCK_ALL_LOCAL)
            result = get_remote_input_names(lock)
        self.assertEqual(result, [])

    def test_missing_type_treated_as_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            lock = _write_lock(Path(d), LOCK_NO_TYPE)
            result = get_remote_input_names(lock)
        self.assertEqual(result, [])


class TestMain(unittest.TestCase):
    def test_prints_space_separated(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            # main needs repo markers to find root
            (tmp / "flake.nix").write_text("{}", encoding="utf-8")
            (tmp / "scripts_py").mkdir()
            _write_lock(tmp, LOCK_MIXED)

            import io
            from contextlib import redirect_stdout

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main([], repo_root=tmp)

            self.assertEqual(rc, 0)
            self.assertEqual(buf.getvalue().strip(), "home-manager nixpkgs")

    def test_bad_json_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / "flake.lock").write_text("not json", encoding="utf-8")
            rc = main([], repo_root=tmp)
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()

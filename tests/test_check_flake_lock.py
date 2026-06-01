from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts_py.cli.check_flake_lock import (
    check_lock_completeness,
    get_locked_input_names,
    main,
    parse_flake_input_names,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SIMPLE_FLAKE_NIX = """
{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    my-local.url = "path:/home/user/Koodit/my-local";
  };

  outputs = { self, nixpkgs, home-manager, my-local, ... }: {};
}
"""

SIMPLE_FLAKE_LOCK_COMPLETE: dict[str, Any] = json.loads("""
{
  "nodes": {
    "nixpkgs": {"locked": {}, "original": {}},
    "home-manager": {"locked": {}, "original": {}},
    "my-local": {"locked": {}, "original": {}},
    "root": {
      "inputs": {
        "nixpkgs": "nixpkgs",
        "home-manager": "home-manager",
        "my-local": "my-local"
      }
    }
  },
  "root": "root",
  "version": 7
}
""")

SIMPLE_FLAKE_LOCK_MISSING: dict[str, Any] = json.loads("""
{
  "nodes": {
    "nixpkgs": {"locked": {}, "original": {}},
    "home-manager": {"locked": {}, "original": {}},
    "root": {
      "inputs": {
        "nixpkgs": "nixpkgs",
        "home-manager": "home-manager"
      }
    }
  },
  "root": "root",
  "version": 7
}
""")


def _write_lock(tmp: Path, data: dict[str, Any]) -> Path:
    p = tmp / "flake.lock"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# parse_flake_input_names
# ---------------------------------------------------------------------------


class TestParseFlakeInputNames(unittest.TestCase):
    def test_extracts_dotted_form(self) -> None:
        nix = 'inputs = { nixpkgs.url = "..."; };'
        self.assertIn("nixpkgs", parse_flake_input_names(nix))

    def test_extracts_block_form(self) -> None:
        nix = 'inputs = { home-manager = { url = "..."; }; };'
        self.assertIn("home-manager", parse_flake_input_names(nix))

    def test_does_not_include_nested_url_key(self) -> None:
        nix = 'inputs = { home-manager = { url = "..."; }; };'
        self.assertNotIn("url", parse_flake_input_names(nix))

    def test_does_not_include_follows_key(self) -> None:
        nix = """
        inputs = {
          home-manager = {
            url = "...";
            inputs.nixpkgs.follows = "nixpkgs";
          };
        };
        """
        names = parse_flake_input_names(nix)
        self.assertNotIn("inputs", names)
        self.assertNotIn("nixpkgs", names)

    def test_handles_hyphenated_names(self) -> None:
        nix = 'inputs = { nix-dokploy.url = "..."; };'
        self.assertIn("nix-dokploy", parse_flake_input_names(nix))

    def test_handles_multiple_inputs(self) -> None:
        names = parse_flake_input_names(SIMPLE_FLAKE_NIX)
        self.assertEqual(names, {"nixpkgs", "home-manager", "my-local"})

    def test_no_inputs_block_returns_empty(self) -> None:
        self.assertEqual(parse_flake_input_names("{ outputs = _: {}; }"), set())

    def test_skips_line_comments(self) -> None:
        nix = """
        inputs = {
          # nixpkgs is locked elsewhere
          nixpkgs.url = "...";
        };
        """
        names = parse_flake_input_names(nix)
        self.assertIn("nixpkgs", names)
        self.assertNotIn("nixpkgs is locked elsewhere", names)

    def test_string_braces_do_not_confuse_depth(self) -> None:
        # A URL containing { or } (unusual but defensive)
        nix = 'inputs = { weird.url = "path:/some/{dir}"; other.url = "x"; };'
        names = parse_flake_input_names(nix)
        self.assertIn("weird", names)
        self.assertIn("other", names)

    def test_path_url_input(self) -> None:
        nix = 'inputs = { my-local.url = "path:/home/user/Koodit/my-local"; };'
        self.assertIn("my-local", parse_flake_input_names(nix))


# ---------------------------------------------------------------------------
# get_locked_input_names
# ---------------------------------------------------------------------------


class TestGetLockedInputNames(unittest.TestCase):
    def test_returns_root_inputs_keys(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = _write_lock(Path(d), SIMPLE_FLAKE_LOCK_COMPLETE)
            result = get_locked_input_names(p)
        self.assertEqual(result, {"nixpkgs", "home-manager", "my-local"})

    def test_returns_none_for_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "flake.lock"
            p.write_text("not json", encoding="utf-8")
            self.assertIsNone(get_locked_input_names(p))

    def test_returns_none_for_missing_file(self) -> None:
        self.assertIsNone(get_locked_input_names(Path("/does/not/exist/flake.lock")))

    def test_returns_none_for_missing_nodes_key(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "flake.lock"
            p.write_text(json.dumps({"version": 7}), encoding="utf-8")
            self.assertIsNone(get_locked_input_names(p))

    def test_returns_empty_set_when_no_root_inputs(self) -> None:
        data: dict[str, Any] = json.loads(
            '{"nodes": {"root": {"inputs": {}}}, "root": "root", "version": 7}'
        )
        with tempfile.TemporaryDirectory() as d:
            p = _write_lock(Path(d), data)
            self.assertEqual(get_locked_input_names(p), set())


# ---------------------------------------------------------------------------
# check_lock_completeness
# ---------------------------------------------------------------------------


class TestCheckLockCompleteness(unittest.TestCase):
    def test_ok_when_all_inputs_locked(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            lock = _write_lock(Path(d), SIMPLE_FLAKE_LOCK_COMPLETE)
            ok, _ = check_lock_completeness(SIMPLE_FLAKE_NIX, lock)
        self.assertTrue(ok)

    def test_fails_when_input_missing_from_lock(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            lock = _write_lock(Path(d), SIMPLE_FLAKE_LOCK_MISSING)
            ok, msg = check_lock_completeness(SIMPLE_FLAKE_NIX, lock)
        self.assertFalse(ok)
        self.assertIn("my-local", msg)

    def test_failure_message_mentions_nix_flake_lock(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            lock = _write_lock(Path(d), SIMPLE_FLAKE_LOCK_MISSING)
            ok, msg = check_lock_completeness(SIMPLE_FLAKE_NIX, lock)
        self.assertFalse(ok)
        self.assertIn("nix flake lock", msg)

    def test_ok_when_no_inputs_block(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            lock = _write_lock(Path(d), SIMPLE_FLAKE_LOCK_COMPLETE)
            ok, _ = check_lock_completeness("{ outputs = _: {}; }", lock)
        self.assertTrue(ok)

    def test_fails_when_lock_unparseable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "flake.lock"
            p.write_text("broken", encoding="utf-8")
            ok, _ = check_lock_completeness(SIMPLE_FLAKE_NIX, p)
        self.assertFalse(ok)

    def test_reports_all_missing_inputs(self) -> None:
        nix = """
        inputs = {
          a.url = "...";
          b.url = "...";
          c.url = "...";
        };
        """
        lock_data: dict[str, Any] = json.loads(
            '{"nodes": {"root": {"inputs": {"a": "a"}}, "a": {}}, "root": "root", "version": 7}'
        )
        with tempfile.TemporaryDirectory() as d:
            lock = _write_lock(Path(d), lock_data)
            ok, msg = check_lock_completeness(nix, lock)
        self.assertFalse(ok)
        self.assertIn("b", msg)
        self.assertIn("c", msg)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


class TestMain(unittest.TestCase):
    def test_returns_0_when_lock_is_complete(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            (dp / "flake.nix").write_text(SIMPLE_FLAKE_NIX, encoding="utf-8")
            _write_lock(dp, SIMPLE_FLAKE_LOCK_COMPLETE)
            # Provide a dummy pyproject.toml so repo_root_from_script_path finds d.
            (dp / "pyproject.toml").write_text("[tool.pytest]", encoding="utf-8")
            rc = main(repo_root=dp)
        self.assertEqual(rc, 0)

    def test_returns_1_when_lock_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            (dp / "flake.nix").write_text(SIMPLE_FLAKE_NIX, encoding="utf-8")
            _write_lock(dp, SIMPLE_FLAKE_LOCK_MISSING)
            (dp / "pyproject.toml").write_text("[tool.pytest]", encoding="utf-8")
            rc = main(repo_root=dp)
        self.assertEqual(rc, 1)

    def test_returns_2_when_flake_nix_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            _write_lock(dp, SIMPLE_FLAKE_LOCK_COMPLETE)
            rc = main(repo_root=dp)
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()

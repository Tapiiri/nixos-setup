from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from scripts_py.devshell import REPO_MARKERS, build_nix_develop_command, compute_config, parse_args
from scripts_py.utils import find_upwards


class TestDevshell(unittest.TestCase):
    def test_find_repo_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "repo"
            root.mkdir()
            (root / "flake.nix").write_text("{}", encoding="utf-8")
            (root / "scripts_py").mkdir()
            (root / "dev").mkdir()

            nested = root / "a" / "b" / "c"
            nested.mkdir(parents=True)

            found = find_upwards(nested, markers=REPO_MARKERS)
            self.assertEqual(found, root)

    def test_parse_args_passthrough(self):
        args, rest = parse_args(["-c", "pytest -q", "--print-build-logs"])
        self.assertEqual(args.command, "pytest -q")
        self.assertEqual(rest, ["--print-build-logs"])

    def test_build_command_interactive(self):
        cfg = type("Cfg", (), {"repo_root": Path("/x")})()
        cmd = build_nix_develop_command(cfg, command=None, passthrough=["--impure"])
        self.assertEqual(cmd, ["nix", "develop", "/x/dev", "--impure"])

    def test_build_command_one_shot(self):
        cfg = type("Cfg", (), {"repo_root": Path("/x")})()
        cmd = build_nix_develop_command(cfg, command="pytest -q", passthrough=["--impure"])
        self.assertEqual(
            cmd,
            ["nix", "develop", "/x/dev", "-c", "bash", "-lc", "pytest -q", "--impure"],
        )

    def test_compute_config_errors_when_missing(self):
        with tempfile.TemporaryDirectory() as td:
            # Place script somewhere not inside a repo
            script_path = Path(td) / "scripts" / "devshell.py"
            script_path.parent.mkdir(parents=True)
            script_path.write_text("#", encoding="utf-8")

            with self.assertRaises(FileNotFoundError):
                compute_config(script_path=script_path)

    def test_empty_c_returns_2_in_main(self):
        # Import main lazily so the module can be used without extra deps.
        from scripts_py import devshell as mod

        class CapturingRunner:
            def exec(self, argv):
                raise AssertionError("should not exec")

        stderr = io.StringIO()
        rc = mod.main(["-c", "  "], runner=CapturingRunner(), stderr=stderr)
        self.assertEqual(rc, 2)
        self.assertIn("usage:", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()

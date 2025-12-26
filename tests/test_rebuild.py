from __future__ import annotations

import tempfile
import unittest
import os
from pathlib import Path

from scripts_py.rebuild import (
    RebuildConfig,
    build_exec_command,
    build_nixos_rebuild_command,
    compute_config,
    parse_args,
)


def write_hostname(tmp_dir: Path, value: str) -> Path:
    p = tmp_dir / "hostname"
    p.write_text(value, encoding="utf-8")
    return p


class TestRebuild(unittest.TestCase):
    def test_parse_args_rejects_unknown_option_without_double_dash(self):
        with self.assertRaises(SystemExit):
            parse_args(["--nope"])

    def test_parse_args_allows_passthrough_after_double_dash(self):
        args, rest = parse_args(["--dev", "myhost", "--", "--show-trace", "-L"])
        self.assertTrue(args.dev)
        self.assertEqual(args.hostname, "myhost")
        self.assertEqual(rest, ["--show-trace", "-L"])

    def test_parse_args_supports_sync_flags(self):
        args, _rest = parse_args(["--sync", "--sync-ref", "origin/main", "myhost"])
        self.assertEqual(args.hostname, "myhost")
        self.assertTrue(args.sync)
        self.assertEqual(args.sync_ref, "origin/main")
        self.assertFalse(args.sync_checkout)

        args2, _rest2 = parse_args(["--no-sync", "myhost"])
        self.assertFalse(args2.sync)

    def test_compute_config_infers_hostname_and_dev_flake(self):
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)

            # Arrange: fake repo root with flake.nix
            repo_root = tmp_path / "repo"
            repo_root.mkdir()
            (repo_root / "flake.nix").write_text("{}", encoding="utf-8")

            # Place a fake script under repo_root/scripts_py
            script_dir = repo_root / "scripts_py"
            script_dir.mkdir()
            script_path = script_dir / "rebuild.py"
            script_path.write_text("#", encoding="utf-8")

            hostname_path = write_hostname(tmp_path, " testhost \n")

            ns, _rest = parse_args(["--dev"])  # no hostname
            cfg = compute_config(args=ns, script_path=script_path, hostname_path=hostname_path)

            self.assertEqual(cfg.hostname, "testhost")
            self.assertEqual(cfg.flake_dir, repo_root)
            self.assertFalse(cfg.sync_etc_nixos)
            self.assertFalse(cfg.sync_checkout)

    def test_compute_config_errors_when_flake_missing(self):
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)

            repo_root = tmp_path / "repo"
            repo_root.mkdir()
            script_dir = repo_root / "scripts_py"
            script_dir.mkdir()
            script_path = script_dir / "rebuild.py"
            script_path.write_text("#", encoding="utf-8")

            ns, _rest = parse_args(["--dev", "myhost"])
            with self.assertRaises(FileNotFoundError):
                compute_config(args=ns, script_path=script_path, hostname_path=tmp_path / "hostname")

    def test_build_command_shape(self):
        cfg = RebuildConfig(
            hostname="h",
            flake_dir=Path("/etc/nixos"),
            repo_root=Path("/x"),
            sync_etc_nixos=True,
            sync_ref="origin/main",
            sync_checkout=False,
        )
        cmd = build_nixos_rebuild_command(cfg, ["--show-trace"])
        self.assertEqual(cmd[:4], ["nixos-rebuild", "switch", "--flake", "/etc/nixos/.#h"])
        self.assertEqual(cmd[4:], ["--show-trace"])

    def test_build_exec_command_adds_sudo_when_not_root(self):
        # We can't rely on the test runner uid always being non-root, so test
        # both branches by patching os.geteuid.
        from unittest.mock import patch

        base = ["nixos-rebuild", "switch"]
        with patch("os.geteuid", return_value=1000):
            self.assertEqual(build_exec_command(base)[:2], ["sudo", "nixos-rebuild"])
        with patch("os.geteuid", return_value=0):
            self.assertEqual(build_exec_command(base), base)

    def test_entrypoint_bootstraps_when_symlinked(self):
        """Simulate PATH installation: symlink entrypoint outside repo.

        We don't actually exec nixos-rebuild; we just check it can import
        `scripts_py.rebuild` and show help.
        """

        import subprocess
        import sys
        import tempfile

        repo_root = Path(__file__).resolve().parent.parent
        entry = repo_root / "scripts" / "rebuild"

        with tempfile.TemporaryDirectory() as td:
            bin_dir = Path(td) / "bin"
            bin_dir.mkdir()
            link = bin_dir / "rebuild"
            link.symlink_to(entry)

            cp = subprocess.run(
                [str(link), "--help"],
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={"PATH": os.environ.get("PATH", ""), "PYTHONNOUSERSITE": "1"},
            )
            # argparse prints help to stdout (lowercase 'usage:' by default)
            self.assertIn("usage: rebuild", cp.stdout.lower())



if __name__ == "__main__":
    unittest.main()

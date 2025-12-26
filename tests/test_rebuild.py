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
    root_set_origin_to_mirror,
    root_ensure_etc_nixos_clone,
    root_update_from_mirror,
    mirror_push_from_dev,
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

    def test_parse_args_defaults_for_mirror_flags(self):
        args, _rest = parse_args(["myhost"])
        self.assertEqual(args.hostname, "myhost")
        self.assertFalse(args.mirror)
        self.assertFalse(args.offline_ok)

        # New opt-out flag
        args2, _rest2 = parse_args(["--no-mirror", "myhost"])
        self.assertTrue(args2.no_mirror)

    def test_parse_args_supports_mirror_flags(self):
        args, _rest = parse_args(["--mirror", "--offline-ok", "--mirror-dir", "/x/mirror.git", "myhost"])
        self.assertTrue(args.mirror)
        self.assertTrue(args.offline_ok)
        self.assertEqual(str(args.mirror_dir), "/x/mirror.git")

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
            self.assertFalse(cfg.use_mirror)
            self.assertTrue(str(cfg.mirror_dir).endswith("/var/lib/nixos-setup/mirror.git"))
            self.assertFalse(cfg.offline_ok)

    def test_compute_config_defaults_to_mirror_when_not_dev(self):
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

            # Also fake a flake dir with flake.nix
            etc_dir = tmp_path / "etc-nixos"
            etc_dir.mkdir()
            (etc_dir / "flake.nix").write_text("{}", encoding="utf-8")

            hostname_path = write_hostname(tmp_path, "testhost\n")
            ns, _rest = parse_args(["--flake", str(etc_dir)])
            cfg = compute_config(args=ns, script_path=script_path, hostname_path=hostname_path)
            self.assertTrue(cfg.use_mirror)

            ns2, _rest2 = parse_args(["--flake", str(etc_dir), "--no-mirror"])
            cfg2 = compute_config(args=ns2, script_path=script_path, hostname_path=hostname_path)
            self.assertFalse(cfg2.use_mirror)

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
            use_mirror=False,
            mirror_dir=Path("/var/lib/nixos-setup/mirror.git"),
            offline_ok=False,
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

    def test_root_set_origin_to_mirror_sets_origin_url(self):
        from unittest.mock import patch

        calls: list[list[str]] = []

        def fake_run(argv, **kwargs):
            calls.append(list(argv))
            # `remote get-url origin` returns a GitHub SSH URL
            if argv[:6] == ["sudo", "git", "-C", "/etc/nixos", "remote", "get-url"]:
                return type(
                    "CP",
                    (),
                    {"returncode": 0, "stdout": "git@github.com:Tapiiri/nixos-setup.git\n", "stderr": ""},
                )()
            return type("CP", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with patch("subprocess.run", side_effect=fake_run):
            rc = root_set_origin_to_mirror(
                etc_dir=Path("/etc/nixos"),
                mirror_dir=Path("/var/lib/nixos-setup/mirror.git"),
                stderr=None,
            )

        self.assertEqual(rc, 0)
        self.assertIn(
            [
                "sudo",
                "git",
                "-C",
                "/etc/nixos",
                "remote",
                "set-url",
                "origin",
                "/var/lib/nixos-setup/mirror.git",
            ],
            calls,
        )

    def test_root_update_from_mirror_fetches_origin_no_github(self):
        from unittest.mock import patch

        calls: list[list[str]] = []

        def fake_run(argv, **kwargs):
            calls.append(list(argv))
            # origin already points to local mirror
            if argv[:6] == ["sudo", "git", "-C", "/etc/nixos", "remote", "get-url"]:
                return type(
                    "CP",
                    (),
                    {"returncode": 0, "stdout": "/var/lib/nixos-setup/mirror.git\n", "stderr": ""},
                )()
            return type("CP", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with patch("subprocess.run", side_effect=fake_run):
            rc = root_update_from_mirror(
                etc_dir=Path("/etc/nixos"),
                mirror_dir=Path("/var/lib/nixos-setup/mirror.git"),
                ref="origin/main",
                stderr=None,
            )

        self.assertEqual(rc, 0)
        flat = "\n".join(" ".join(c) for c in calls)
        self.assertNotIn("github.com", flat)
        self.assertIn("fetch --prune origin", flat)
        self.assertIn("merge --ff-only origin/main", flat)

    def test_root_ensure_etc_nixos_clone_moves_aside_non_git_dir(self):
        from unittest.mock import patch

        calls: list[list[str]] = []

        def fake_run(argv, **kwargs):
            calls.append(list(argv))
            # mv and git clone both succeed
            return type("CP", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with tempfile.TemporaryDirectory() as td:
            etc_dir = Path(td) / "etc-nixos"
            etc_dir.mkdir()
            # make it look like a partially-created /etc/nixos (has flake.nix, no .git)
            (etc_dir / "flake.nix").write_text("{}", encoding="utf-8")

            with patch("subprocess.run", side_effect=fake_run):
                rc = root_ensure_etc_nixos_clone(
                    mirror_dir=Path("/var/lib/nixos-setup/mirror.git"),
                    etc_dir=etc_dir,
                    stderr=None,
                )

        self.assertEqual(rc, 0)
        flat = "\n".join(" ".join(c) for c in calls)
        self.assertIn("sudo mv --", flat)
        self.assertIn("sudo git clone /var/lib/nixos-setup/mirror.git", flat)

    def test_mirror_push_from_dev_pushes_branch_to_mirror(self):
        from unittest.mock import patch

        calls: list[list[str]] = []

        def fake_run(argv, **kwargs):
            calls.append(list(argv))
            # rev-parse ok
            if argv[:5] == ["git", "-C", "/repo", "rev-parse", "--verify"]:
                return type("CP", (), {"returncode": 0, "stdout": "deadbeef\n", "stderr": ""})()
            # push ok
            return type("CP", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with patch("subprocess.run", side_effect=fake_run):
            rc = mirror_push_from_dev(repo_root=Path("/repo"), mirror_dir=Path("/mirror.git"), branch="main", stderr=None)

        self.assertEqual(rc, 0)
        flat = "\n".join(" ".join(c) for c in calls)
        self.assertIn("git -C /repo push /mirror.git refs/heads/main:refs/heads/main", flat)

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

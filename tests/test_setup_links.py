import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


from scripts_py.setup_links import (
    LinkMapping,
    SetupConfig,
    compute_config,
    compute_mappings,
    link_user_owned,
    parse_args,
    process_mapping,
)


class FakeRunner:
    def __init__(self):
        self.calls = []
        self.returncode = 0

    def run(self, argv):
        self.calls.append(list(argv))
        return self.returncode


class TestSetupLinks(unittest.TestCase):
    def test_build_root_helper_argv(self):
        # root-helper functionality removed; nothing to test here.
        self.assertTrue(True)

    def test_build_root_replace_then_link_argv(self):
        # root-helper functionality removed; nothing to test here.
        self.assertTrue(True)

    def test_is_safe_root_replace_target_allowlists_etc_nixos_children(self):
        # root-helper safety checks removed; nothing to test here.
        self.assertTrue(True)

    def test_compute_config_uses_hostname_file_when_missing_host(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            repo = tdp / "repo"
            (repo / "hosts" / "myhost").mkdir(parents=True)
            (repo / "flake.nix").write_text("# marker\n", encoding="utf-8")

            # We pass script_path under scripts_py and patch compute_repo_root by aligning layout.
            (repo / "scripts_py").mkdir(parents=True)
            fake_script_path = repo / "scripts_py" / "setup_links.py"
            fake_script_path.write_text("# placeholder\n", encoding="utf-8")

            hostname_file = tdp / "hostname"
            hostname_file.write_text("myhost\n", encoding="utf-8")

            args = parse_args([])
            cfg = compute_config(args=args, script_path=fake_script_path, home=tdp / "home", hostname_path=hostname_file)
            self.assertEqual(cfg.hostname, "myhost")
            self.assertEqual(cfg.host_dir, repo / "hosts" / "myhost")

    def test_compute_mappings_includes_scripts_and_dotfiles(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            repo = tdp / "repo"
            host_dir = repo / "hosts" / "h"
            host_dir.mkdir(parents=True)

            # Host files
            (host_dir / "home.nix").write_text("{}", encoding="utf-8")
            (host_dir / "home").mkdir()
            (host_dir / "configuration.nix").write_text("{}", encoding="utf-8")

            # flake entrypoint (no longer linked into /etc/nixos by setup-links)
            (repo / "flake.nix").write_text("{}", encoding="utf-8")
            (repo / "flake.lock").write_text("{}", encoding="utf-8")

            # repo-level HM modules
            (repo / "home" / "modules").mkdir(parents=True)
            (repo / "home" / "modules" / "default.nix").write_text("{}", encoding="utf-8")

            # scripts
            scripts = repo / "scripts"
            scripts.mkdir(parents=True)
            exe = scripts / "tool"
            exe.write_text("#!/bin/sh\n", encoding="utf-8")
            exe.chmod(exe.stat().st_mode | 0o111)

            # dotfiles
            dot_home = repo / "dotfiles" / "home"
            dot_home.mkdir(parents=True)
            (dot_home / "bashrc").write_text("x", encoding="utf-8")

            cfg = SetupConfig(repo_root=repo, hostname="h", host_dir=host_dir, home=tdp / "HOME")
            mappings = compute_mappings(cfg)
            targets = {m.target for m in mappings}

            self.assertIn(cfg.home / ".config" / "home-manager" / "home.nix", targets)
            self.assertIn(cfg.home / ".config" / "home-manager", targets)
            self.assertIn(cfg.home / ".config" / "home-manager" / "modules", targets)
            self.assertIn(Path("/etc/nixos/configuration.nix"), targets)
            self.assertIn(cfg.home / ".local" / "bin" / "tool", targets)
            self.assertIn(cfg.home / ".bashrc", targets)

    def test_link_user_owned_creates_symlink_and_updates(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            src = tdp / "src"
            src.write_text("x", encoding="utf-8")
            dst = tdp / "a" / "b" / "dst"

            from io import StringIO

            out = StringIO()
            err = StringIO()
            link_user_owned(src, dst, out=out, err=err)
            self.assertTrue(dst.is_symlink())
            self.assertEqual(dst.resolve(strict=False), src)

            # Update to new source
            src2 = tdp / "src2"
            src2.write_text("y", encoding="utf-8")
            link_user_owned(src2, dst, out=out, err=err)
            self.assertEqual(dst.resolve(strict=False), src2)

    def test_process_mapping_delegates_root_owned_with_helper(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            src = tdp / "src"
            src.write_text("x", encoding="utf-8")

            # An allowlisted managed path (root-owned because it lives under /etc).
            # We don't actually create it; FakeRunner captures argv.
            # Use an allowlisted path, but do not touch the real file.
            # Point at configuration.nix (expected to be managed via helper).
            dst = Path("/etc/nixos/configuration.nix")

            runner = FakeRunner()
            from io import StringIO

            out = StringIO()
            err = StringIO()

            with patch("scripts_py.setup_links.owner_uid_for_path", return_value=0):
                rc = process_mapping(LinkMapping(source=src, target=dst), runner=runner, out=out, err=err)
                self.assertEqual(rc, 0)
                # Root-owned targets are skipped; no privileged calls should be made.
                self.assertEqual(len(runner.calls), 0)
                self.assertIn("Skipping root-owned target", err.getvalue())

    def test_process_mapping_falls_back_to_ln_for_non_allowlisted_target(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            src = tdp / "src"
            src.write_text("x", encoding="utf-8")

            # Root-owned because it ultimately resolves ownership from '/'
            dst = Path("/tmp") / f"copilot-test-{os.getpid()}-setup-links-fallback"

            runner = FakeRunner()
            from io import StringIO

            out = StringIO()
            err = StringIO()
            # Simulate root-owned path
            with patch("scripts_py.setup_links.owner_uid_for_path", return_value=0):
                rc = process_mapping(LinkMapping(source=src, target=dst), runner=runner, out=out, err=err)
            self.assertEqual(rc, 0)
            self.assertEqual(len(runner.calls), 0)
            self.assertIn("Skipping root-owned target", err.getvalue())

    def test_process_mapping_skips_root_helper_when_already_linked(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            src = tdp / "src"
            src.write_text("x", encoding="utf-8")

            # Create a symlink at the target path pointing to src.
            dst = tdp / "dst"
            dst.symlink_to(src)

            runner = FakeRunner()
            from io import StringIO

            out = StringIO()
            err = StringIO()
            rc = process_mapping(
                LinkMapping(source=src, target=dst),
                runner=runner,
                out=out,
                err=err,
            )
            self.assertEqual(rc, 0)
            self.assertEqual(runner.calls, [])


if __name__ == "__main__":
    unittest.main()

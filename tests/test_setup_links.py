import os
import tempfile
import unittest
from pathlib import Path


from scripts_py.setup_links import (
    LinkMapping,
    SetupConfig,
    build_root_helper_argv,
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
        src = Path("/src")
        dst = Path("/dst")
        self.assertEqual(build_root_helper_argv("sudo", source=src, target=dst)[:2], ["sudo", "ln"])
        self.assertEqual(build_root_helper_argv("doas", source=src, target=dst)[:2], ["doas", "ln"])
        self.assertEqual(
            build_root_helper_argv("sudo --preserve-env", source=src, target=dst)[:3],
            ["sudo", "--preserve-env", "ln"],
        )

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

            cfg = SetupConfig(repo_root=repo, hostname="h", host_dir=host_dir, root_helper=None, home=tdp / "HOME")
            mappings = compute_mappings(cfg)
            targets = {m.target for m in mappings}

            self.assertIn(cfg.home / ".config" / "home-manager" / "home.nix", targets)
            self.assertIn(cfg.home / ".config" / "home-manager", targets)
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

            # A target under an existing root-owned path: / (uid 0)
            dst = Path("/tmp") / f"copilot-test-{os.getpid()}-setup-links"

            runner = FakeRunner()
            from io import StringIO

            out = StringIO()
            err = StringIO()

            rc = process_mapping(
                LinkMapping(source=src, target=dst),
                root_helper="sudo",
                runner=runner,
                out=out,
                err=err,
            )
            self.assertEqual(rc, 0)
            self.assertEqual(len(runner.calls), 1)
            self.assertEqual(runner.calls[0][:2], ["sudo", "ln"])


if __name__ == "__main__":
    unittest.main()

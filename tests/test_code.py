import tempfile
import unittest
from pathlib import Path

from scripts_py.code import (
    DevshellChoice,
    build_exec_argv,
    choose_devshell,
    infer_start_dir,
)


class TestCodeWrapper(unittest.TestCase):
    def test_infer_start_dir_uses_cwd_when_no_path_args(self):
        cwd = Path("/tmp")
        self.assertEqual(infer_start_dir([], cwd=cwd), cwd)

    def test_infer_start_dir_uses_first_non_flag_arg(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            (cwd / "proj").mkdir()
            start = infer_start_dir(["--reuse-window", "proj"], cwd=cwd)
            self.assertEqual(start, (cwd / "proj").resolve())

    def test_choose_devshell_prefers_dev_flake(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "dev").mkdir()
            (root / "dev" / "flake.nix").write_text("# dev flake\n", encoding="utf-8")
            (root / "flake.nix").write_text("# root flake\n", encoding="utf-8")
            (root / "sub").mkdir()

            choice = choose_devshell(root / "sub")
            self.assertIsNotNone(choice)
            assert choice is not None
            self.assertEqual(choice.flake_path, root / "dev")

    def test_choose_devshell_falls_back_to_root_flake(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "flake.nix").write_text("# root flake\n", encoding="utf-8")
            (root / "sub").mkdir()

            choice = choose_devshell(root / "sub")
            self.assertIsNotNone(choice)
            assert choice is not None
            self.assertEqual(choice.flake_path, root)

    def test_build_exec_argv_without_devshell(self):
        argv = build_exec_argv(
            real_code=Path("/bin/code"),
            argv=["--version"],
            devshell=None,
        )
        self.assertEqual(argv, ["/bin/code", "--version"])

    def test_build_exec_argv_with_devshell(self):
        argv = build_exec_argv(
            real_code=Path("/bin/code"),
            argv=["--version"],
            devshell=DevshellChoice(flake_path=Path("/repo/dev")),
        )
        self.assertEqual(
            argv,
            [
                "nix",
                "develop",
                "--impure",
                "/repo/dev",
                "-c",
                "/bin/code",
                "--version",
            ],
        )


if __name__ == "__main__":
    unittest.main()

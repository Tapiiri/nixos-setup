from __future__ import annotations

import tempfile
import unittest
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn
from unittest.mock import patch

from scripts_py.cli.hm_switch import (
    ENV_PROFILE,
    HomeManagerSwitchConfig,
    build_home_manager_switch_command,
    compute_config,
    default_profile,
    main,
    parse_args,
)


class RecordingRunner:
    def __init__(self) -> None:
        self.argv: list[str] | None = None

    def exec(self, argv: Sequence[str]) -> NoReturn:
        self.argv = list(argv)
        raise SystemExit(0)


class TestHomeManagerSwitch(unittest.TestCase):
    def test_parse_args_rejects_unknown_option_without_double_dash(self):
        with self.assertRaises(SystemExit):
            parse_args(["--nope"])

    def test_parse_args_allows_passthrough_after_double_dash(self):
        args, rest = parse_args(["tapiiri", "--", "--show-trace", "-L"])
        self.assertEqual(args.profile, "tapiiri")
        self.assertEqual(rest, ["--show-trace", "-L"])

    def test_default_profile_prefers_explicit_env(self):
        self.assertEqual(
            default_profile(env={ENV_PROFILE: "tapiiri-wsl", "USER": "someone"}),
            "tapiiri-wsl",
        )

    def test_default_profile_falls_back_to_user(self):
        self.assertEqual(default_profile(env={"USER": "tapiiri"}), "tapiiri")

    def test_compute_config_defaults_to_repo_root_flake(self):
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)

            repo_root = tmp_path / "repo"
            repo_root.mkdir()
            (repo_root / "flake.nix").write_text("{}", encoding="utf-8")

            script_dir = repo_root / "scripts_py" / "cli"
            script_dir.mkdir(parents=True)
            script_path = script_dir / "hm_switch.py"
            script_path.write_text("#", encoding="utf-8")

            args, _rest = parse_args([])
            cfg = compute_config(args=args, script_path=script_path, env={"USER": "tapiiri"})

            self.assertEqual(cfg.profile, "tapiiri")
            self.assertEqual(cfg.flake_dir, repo_root)
            self.assertIsNone(cfg.backup_extension)

    def test_compute_config_requires_a_profile(self):
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)

            repo_root = tmp_path / "repo"
            repo_root.mkdir()
            (repo_root / "flake.nix").write_text("{}", encoding="utf-8")

            script_dir = repo_root / "scripts_py" / "cli"
            script_dir.mkdir(parents=True)
            script_path = script_dir / "hm_switch.py"
            script_path.write_text("#", encoding="utf-8")

            args, _rest = parse_args([])
            with patch("scripts_py.cli.hm_switch.Path.home", return_value=Path("/")):
                with self.assertRaises(ValueError):
                    compute_config(args=args, script_path=script_path, env={})

    def test_compute_config_errors_when_flake_missing(self):
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)

            repo_root = tmp_path / "repo"
            repo_root.mkdir()

            script_dir = repo_root / "scripts_py" / "cli"
            script_dir.mkdir(parents=True)
            script_path = script_dir / "hm_switch.py"
            script_path.write_text("#", encoding="utf-8")

            args, _rest = parse_args(["tapiiri"])
            with self.assertRaises(FileNotFoundError):
                compute_config(args=args, script_path=script_path, env={})

    def test_build_command_shape(self):
        cfg = HomeManagerSwitchConfig(
            profile="tapiiri",
            flake_dir=Path("/repo"),
            repo_root=Path("/repo"),
            backup_extension="backup",
        )
        self.assertEqual(
            build_home_manager_switch_command(cfg, ["--show-trace"]),
            [
                "home-manager",
                "switch",
                "--flake",
                "/repo#tapiiri",
                "-b",
                "backup",
                "--show-trace",
            ],
        )

    def test_main_execs_expected_command(self):
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)

            repo_root = tmp_path / "repo"
            repo_root.mkdir()
            (repo_root / "flake.nix").write_text("{}", encoding="utf-8")

            script_dir = repo_root / "scripts_py" / "cli"
            script_dir.mkdir(parents=True)
            script_path = script_dir / "hm_switch.py"
            script_path.write_text("#", encoding="utf-8")

            runner = RecordingRunner()
            with self.assertRaises(SystemExit):
                main(
                    argv=["tapiiri", "-b", "backup", "--", "--show-trace"],
                    runner=runner,
                    script_path=script_path,
                    env={},
                )

            self.assertEqual(
                runner.argv,
                [
                    "home-manager",
                    "switch",
                    "--flake",
                    f"{repo_root}#tapiiri",
                    "-b",
                    "backup",
                    "--show-trace",
                ],
            )


if __name__ == "__main__":
    unittest.main()

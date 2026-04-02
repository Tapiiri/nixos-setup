from __future__ import annotations

import tempfile
import unittest
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn
from unittest.mock import patch

from scripts_py.cli.hm_switch import (
    ENV_FLAKE_URI,
    ENV_PROFILE,
    NIX_EXPERIMENTAL_FEATURES,
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

    def test_default_profile_returns_none_without_env(self):
        self.assertIsNone(default_profile(env={"USER": "tapiiri"}))

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
            cfg = compute_config(
                args=args,
                script_path=script_path,
                env={ENV_PROFILE: "tapiiri"},
            )

            self.assertEqual(cfg.profile, "tapiiri")
            self.assertEqual(cfg.flake_ref, str(repo_root))
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

    def test_compute_config_uses_flake_uri_env_var(self):
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)

            # No repo markers at all — env var should be the sole source.
            script_path = tmp_path / "hm_switch.py"
            script_path.write_text("#", encoding="utf-8")

            args, _rest = parse_args(["tapiiri-wsl"])
            cfg = compute_config(
                args=args,
                script_path=script_path,
                env={
                    ENV_FLAKE_URI: "github:Tapiiri/nixos-setup",
                    "USER": "tapiiri",
                },
            )

            self.assertEqual(cfg.profile, "tapiiri-wsl")
            self.assertEqual(cfg.flake_ref, "github:Tapiiri/nixos-setup")

    def test_compute_config_flake_arg_overrides_env(self):
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)

            local_dir = tmp_path / "local"
            local_dir.mkdir()
            (local_dir / "flake.nix").write_text("{}", encoding="utf-8")

            script_path = tmp_path / "hm_switch.py"
            script_path.write_text("#", encoding="utf-8")

            args, _rest = parse_args(["--flake", str(local_dir), "tapiiri"])
            cfg = compute_config(
                args=args,
                script_path=script_path,
                env={
                    ENV_FLAKE_URI: "github:Tapiiri/nixos-setup",
                    "USER": "tapiiri",
                },
            )

            self.assertEqual(cfg.flake_ref, str(local_dir))

    def test_compute_config_errors_without_flake_source(self):
        """No env var, no repo markers → helpful error."""
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)

            script_path = tmp_path / "hm_switch.py"
            script_path.write_text("#", encoding="utf-8")

            args, _rest = parse_args(["tapiiri"])
            with self.assertRaises(FileNotFoundError) as ctx:
                compute_config(args=args, script_path=script_path, env={})
            self.assertIn("NIXOS_SETUP_FLAKE_URI", str(ctx.exception))

    def test_build_command_shape(self):
        cfg = HomeManagerSwitchConfig(
            profile="tapiiri",
            flake_ref="/repo",
            backup_extension="backup",
        )
        with patch("scripts_py.cli.hm_switch.shutil.which", return_value="/bin/home-manager"):
            self.assertEqual(
                build_home_manager_switch_command(cfg, ["--show-trace"], env={"PATH": "/bin"}),
                [
                    "/bin/home-manager",
                    "switch",
                    "--flake",
                    "/repo#tapiiri",
                    "-b",
                    "backup",
                    "--show-trace",
                ],
            )

    def test_build_command_falls_back_to_nix_run(self):
        cfg = HomeManagerSwitchConfig(
            profile="tapiiri-wsl",
            flake_ref="/repo",
            backup_extension=None,
        )

        def fake_which(binary: str, path: str | None = None) -> str | None:
            if binary == "home-manager":
                return None
            if binary == "nix":
                return "/nix/bin/nix"
            return None

        with patch("scripts_py.cli.hm_switch.shutil.which", side_effect=fake_which):
            cmd = build_home_manager_switch_command(cfg, [], env={"PATH": "/nix/bin"})

        self.assertEqual(
            cmd,
            [
                "/nix/bin/nix",
                "--extra-experimental-features",
                NIX_EXPERIMENTAL_FEATURES[0],
                "--extra-experimental-features",
                NIX_EXPERIMENTAL_FEATURES[1],
                "run",
                "github:nix-community/home-manager",
                "--",
                "switch",
                "--flake",
                "/repo#tapiiri-wsl",
            ],
        )

    def test_build_command_with_github_flake_ref(self):
        cfg = HomeManagerSwitchConfig(
            profile="tapiiri-wsl",
            flake_ref="github:Tapiiri/nixos-setup",
            backup_extension=None,
        )
        with patch(
            "scripts_py.cli.hm_switch.shutil.which",
            return_value="/bin/home-manager",
        ):
            cmd = build_home_manager_switch_command(cfg, [], env={"PATH": "/bin"})
        self.assertEqual(
            cmd,
            [
                "/bin/home-manager",
                "switch",
                "--flake",
                "github:Tapiiri/nixos-setup#tapiiri-wsl",
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
            with patch("scripts_py.cli.hm_switch.shutil.which", return_value="/bin/home-manager"):
                with self.assertRaises(SystemExit):
                    main(
                        argv=["tapiiri", "-b", "backup", "--", "--show-trace"],
                        runner=runner,
                        script_path=script_path,
                        env={"PATH": "/bin"},
                    )

            self.assertEqual(
                runner.argv,
                [
                    "/bin/home-manager",
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

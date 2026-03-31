from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from scripts_py.lib.utils import OsExecRunner, Runner
from scripts_py.repo.context import repo_root_from_script_path

ENV_PROFILE = "NIXOS_SETUP_HM_PROFILE"


@dataclass(frozen=True)
class HomeManagerSwitchConfig:
    profile: str
    flake_dir: Path
    repo_root: Path
    backup_extension: str | None


def parse_args(argv: Sequence[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        prog="hm-switch",
        add_help=True,
        formatter_class=argparse.RawTextHelpFormatter,
        description=(
            "Run home-manager switch against a standalone nixos-setup profile.\n"
            "If PROFILE is omitted, hm-switch uses NIXOS_SETUP_HM_PROFILE or the current user."
        ),
    )
    parser.add_argument(
        "profile",
        nargs="?",
        help="Standalone Home Manager profile name (defaults to env/current user)",
    )
    parser.add_argument("--flake", type=Path, help="Override flake directory to use")
    parser.add_argument(
        "-b",
        "--backup-extension",
        help="Pass -b EXT to home-manager switch when you want conflicting files backed up",
    )

    args, rest = parser.parse_known_args(list(argv))

    if "--" not in argv:
        for tok in rest:
            if tok.startswith("-"):
                parser.error(f"Unknown option: {tok}")

    if "--" in argv:
        idx = list(argv).index("--")
        rest = list(argv)[idx + 1 :]

    return args, list(rest)


def default_profile(*, env: dict[str, str] | None = None) -> str | None:
    if env is None:
        env = dict(os.environ)

    configured = (env.get(ENV_PROFILE) or "").strip()
    if configured:
        return configured

    user = (env.get("USER") or "").strip()
    if user:
        return user

    try:
        home_name = Path.home().name.strip()
    except RuntimeError:
        return None
    return home_name or None


def compute_config(
    *,
    args: argparse.Namespace,
    script_path: Path,
    env: dict[str, str] | None = None,
) -> HomeManagerSwitchConfig:
    repo_root = repo_root_from_script_path(script_path)
    if env is None:
        env = dict(os.environ)

    profile = (args.profile or default_profile(env=env) or "").strip()
    if not profile:
        raise ValueError(
            "Home Manager profile is required. Pass PROFILE or set NIXOS_SETUP_HM_PROFILE."
        )

    flake_dir = args.flake if args.flake is not None else repo_root
    if not (flake_dir / "flake.nix").is_file():
        raise FileNotFoundError(f"Could not find flake.nix in {flake_dir}")

    return HomeManagerSwitchConfig(
        profile=profile,
        flake_dir=flake_dir,
        repo_root=repo_root,
        backup_extension=(args.backup_extension or "").strip() or None,
    )


def build_home_manager_switch_command(
    cfg: HomeManagerSwitchConfig,
    extra_args: Sequence[str],
) -> list[str]:
    cmd = [
        "home-manager",
        "switch",
        "--flake",
        f"{cfg.flake_dir}#{cfg.profile}",
    ]
    if cfg.backup_extension is not None:
        cmd.extend(["-b", cfg.backup_extension])
    cmd.extend(extra_args)
    return cmd


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: Runner | None = None,
    script_path: Path | None = None,
    env: dict[str, str] | None = None,
) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if runner is None:
        runner = OsExecRunner()
    if script_path is None:
        script_path = Path(__file__)
    if env is None:
        env = dict(os.environ)

    args, rest = parse_args(argv)
    cfg = compute_config(args=args, script_path=script_path, env=env)
    runner.exec(build_home_manager_switch_command(cfg, rest))
    return 0

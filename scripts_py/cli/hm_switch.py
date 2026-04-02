from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from scripts_py.lib.utils import OsExecRunner, Runner
from scripts_py.repo.context import repo_root_from_script_path

ENV_PROFILE = "NIXOS_SETUP_HM_PROFILE"
ENV_FLAKE_URI = "NIXOS_SETUP_FLAKE_URI"
NIX_EXPERIMENTAL_FEATURES = ["nix-command", "flakes"]


@dataclass(frozen=True)
class HomeManagerSwitchConfig:
    profile: str
    flake_ref: str
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
    return configured or None


def compute_config(
    *,
    args: argparse.Namespace,
    script_path: Path,
    env: dict[str, str] | None = None,
) -> HomeManagerSwitchConfig:
    if env is None:
        env = dict(os.environ)

    profile = (args.profile or default_profile(env=env) or "").strip()
    if not profile:
        raise ValueError(
            "Home Manager profile is required. Pass PROFILE as an argument "
            "or set NIXOS_SETUP_HM_PROFILE (reload your shell after first activation)."
        )

    if args.flake is not None:
        flake_ref = str(args.flake)
        flake_path = Path(flake_ref)
        if flake_path.is_dir() and not (flake_path / "flake.nix").is_file():
            raise FileNotFoundError(f"Could not find flake.nix in {flake_path}")
    elif (env.get(ENV_FLAKE_URI) or "").strip():
        flake_ref = env[ENV_FLAKE_URI].strip()
    else:
        try:
            repo_root = repo_root_from_script_path(script_path)
        except FileNotFoundError:
            raise FileNotFoundError(
                "Could not determine flake source. "
                "Set NIXOS_SETUP_FLAKE_URI or run from a repository checkout."
            ) from None
        if not (repo_root / "flake.nix").is_file():
            raise FileNotFoundError(f"Could not find flake.nix in {repo_root}")
        flake_ref = str(repo_root)

    return HomeManagerSwitchConfig(
        profile=profile,
        flake_ref=flake_ref,
        backup_extension=(args.backup_extension or "").strip() or None,
    )


def is_remote_flake_ref(ref: str) -> bool:
    """Return True for non-local flake references (github:, git+https:, etc.)."""
    return ":" in ref and not ref.startswith("/")


def build_home_manager_switch_command(
    cfg: HomeManagerSwitchConfig,
    extra_args: Sequence[str],
    *,
    env: dict[str, str] | None = None,
) -> list[str]:
    if env is None:
        env = dict(os.environ)

    hm_bin = shutil.which("home-manager", path=env.get("PATH"))
    if hm_bin is not None:
        cmd = [
            hm_bin,
            "switch",
            "--flake",
            f"{cfg.flake_ref}#{cfg.profile}",
        ]
        if is_remote_flake_ref(cfg.flake_ref):
            cmd.append("--refresh")
    else:
        nix_bin = shutil.which("nix", path=env.get("PATH"))
        if nix_bin is None:
            raise FileNotFoundError(
                "Could not find either home-manager or nix on PATH. "
                "Install Nix or run inside an environment that provides it."
            )

        cmd = [nix_bin]
        for feature in NIX_EXPERIMENTAL_FEATURES:
            cmd.extend(["--extra-experimental-features", feature])
        if is_remote_flake_ref(cfg.flake_ref):
            cmd.append("--refresh")
        cmd.extend(
            [
                "run",
                "github:nix-community/home-manager",
                "--",
                "switch",
                "--flake",
                f"{cfg.flake_ref}#{cfg.profile}",
            ]
        )

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
    runner.exec(build_home_manager_switch_command(cfg, rest, env=env))
    return 0

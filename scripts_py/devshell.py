from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from scripts_py.utils import OsExecRunner, RepoMarkers, Runner, find_upwards


@dataclass(frozen=True)
class DevshellConfig:
    repo_root: Path


def parse_args(argv: Sequence[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        prog="devshell",
        add_help=True,
        description=(
            "Enter the repo's dev-only nix flake shell interactively.\n"
            "Supports one-shot mode via -c to run a command inside the devshell."
        ),
    )
    parser.add_argument(
        "-c",
        dest="command",
        metavar="CMD",
        help="Run CMD inside the devshell (bash -lc CMD), then exit.",
    )

    # Everything else is passed through to `nix develop ...`.
    args, rest = parser.parse_known_args(list(argv))
    return args, rest


REPO_MARKERS = RepoMarkers(files=("flake.nix",), dirs=("scripts_py", "dev"))


def compute_config(*, script_path: Path) -> DevshellConfig:
    # scripts/devshell -> repo root by default
    repo_guess = script_path.resolve().parent.parent
    repo_root = find_upwards(repo_guess, markers=REPO_MARKERS)

    if repo_root is None:
        # Fall back to walking from the script's directory (covers odd installs/copies).
        repo_root = find_upwards(script_path.resolve().parent, markers=REPO_MARKERS)

    if repo_root is None:
        raise FileNotFoundError(
            "devshell: couldn't locate repo root (expected flake.nix + scripts_py + dev/)"
        )

    return DevshellConfig(repo_root=repo_root)


def build_nix_develop_command(
    cfg: DevshellConfig,
    *,
    command: str | None,
    passthrough: Sequence[str],
) -> list[str]:
    dev_flake = str(cfg.repo_root / "dev")

    if command is not None:
        # Match shell behavior:
        # nix develop <repo>/dev -c bash -lc <cmd> <passthrough...>
        return [
            "nix",
            "develop",
            dev_flake,
            "-c",
            "bash",
            "-lc",
            command,
            *passthrough,
        ]

    return ["nix", "develop", dev_flake, *passthrough]


def main(argv: Sequence[str] | None = None, *, runner: Runner | None = None, stderr=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if runner is None:
        runner = OsExecRunner()
    if stderr is None:
        stderr = sys.stderr

    try:
        args, passthrough = parse_args(argv)
        cfg = compute_config(script_path=Path(__file__))

        if args.command is not None and args.command.strip() == "":
            print("usage: devshell -c '<command>'", file=stderr)
            return 2

        cmd = build_nix_develop_command(cfg, command=args.command, passthrough=passthrough)
    except SystemExit:
        raise
    except Exception as e:
        print(str(e), file=stderr)
        return 1

    runner.exec(cmd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

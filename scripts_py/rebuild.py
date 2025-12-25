from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence


class Runner(Protocol):
    def exec(self, argv: Sequence[str]) -> "NoReturn":  # pragma: no cover
        """Replace current process with argv[0]."""


class OsExecRunner:
    def exec(self, argv: Sequence[str]) -> "NoReturn":
        os.execvp(argv[0], list(argv))
        raise AssertionError("os.execvp returned")


@dataclass(frozen=True)
class RebuildConfig:
    hostname: str
    flake_dir: Path
    repo_root: Path


DEFAULT_SYSTEM_FLAKE_DIR = Path("/etc/nixos")


def _read_hostname(path: Path = Path("/etc/hostname")) -> str | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    host = "".join(ch for ch in raw if ch not in " \t\r\n")
    return host or None


def parse_args(argv: Sequence[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        prog="rebuild",
        add_help=True,
        formatter_class=argparse.RawTextHelpFormatter,
        description=(
            "Run nixos-rebuild switch for the given host using the repository flake.\n"
            "If HOSTNAME is omitted, the current hostname from /etc/hostname is used.\n\n"
            "By default the flake is assumed to live in a root-owned location (a stable\n"
            "system path), so rebuilding still works even if your development checkout is\n"
            "somewhere else."
        ),
    )
    parser.add_argument("--dev", action="store_true", help="Use this repo checkout as the flake source")
    parser.add_argument("--flake", type=Path, help="Override flake directory to use")
    parser.add_argument("hostname", nargs="?", help="Target host (defaults to /etc/hostname)")

    # allow passing through any extra nixos-rebuild flags after `--`
    args, rest = parser.parse_known_args(list(argv))

    # emulate the shell script's behavior: unknown options before `--` are errors
    # parse_known_args will accept them into rest; we reject if rest begins with '-' and no `--` was used.
    # But we can't know if `--` was used in argv; simplest robust rule:
    # If any token in rest starts with '-' and it appeared before a literal `--` in argv, error.
    if "--" not in argv:
        for tok in rest:
            if tok.startswith("-"):
                parser.error(f"Unknown option: {tok}")

    # If there was a `--`, only pass through tokens after it.
    if "--" in argv:
        idx = list(argv).index("--")
        rest = list(argv)[idx + 1 :]

    return args, list(rest)


def compute_repo_root(script_path: Path) -> Path:
    # scripts/rebuild -> repo root
    return script_path.resolve().parent.parent


def compute_config(
    *,
    args: argparse.Namespace,
    script_path: Path,
    hostname_path: Path = Path("/etc/hostname"),
) -> RebuildConfig:
    repo_root = compute_repo_root(script_path)

    hostname = args.hostname or _read_hostname(hostname_path)
    if not hostname:
        raise ValueError("Host name is required and could not be inferred from /etc/hostname")

    if args.flake is not None:
        flake_dir = args.flake
    else:
        flake_dir = repo_root if args.dev else DEFAULT_SYSTEM_FLAKE_DIR

    if not (flake_dir / "flake.nix").is_file():
        hint = None
        if not args.dev and (repo_root / "flake.nix").is_file():
            hint = (
                f"Hint: either link your flake into {DEFAULT_SYSTEM_FLAKE_DIR} or rerun with --dev.\n"
                "      (You can also explicitly set it with --flake PATH.)"
            )
        msg = f"Could not find flake.nix in {flake_dir}"
        if hint:
            msg = msg + "\n" + hint
        raise FileNotFoundError(msg)

    return RebuildConfig(hostname=hostname, flake_dir=flake_dir, repo_root=repo_root)


def build_nixos_rebuild_command(cfg: RebuildConfig, passthrough: Sequence[str]) -> list[str]:
    cmd = [
        "nixos-rebuild",
        "switch",
        "--flake",
        f"{cfg.flake_dir}/.#{cfg.hostname}",
    ]
    cmd.extend(passthrough)
    return cmd


def main(argv: Sequence[str] | None = None, *, runner: Runner | None = None, stderr=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if runner is None:
        runner = OsExecRunner()
    if stderr is None:
        stderr = sys.stderr

    try:
        args, passthrough = parse_args(argv)
        cfg = compute_config(args=args, script_path=Path(__file__))
        cmd = build_nixos_rebuild_command(cfg, passthrough)
    except SystemExit:
        raise
    except Exception as e:
        print(str(e), file=stderr)
        return 1

    print("Running: " + " ".join(cmd), file=stderr)
    runner.exec(cmd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

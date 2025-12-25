from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol, Sequence


class RootCommandRunner(Protocol):
    def run(self, argv: Sequence[str]) -> int:  # pragma: no cover
        """Run a command and return its exit code."""


class SubprocessRunner:
    def run(self, argv: Sequence[str]) -> int:
        cp = subprocess.run(list(argv))
        return int(cp.returncode)


@dataclass(frozen=True)
class LinkMapping:
    source: Path
    target: Path


@dataclass(frozen=True)
class SetupConfig:
    repo_root: Path
    hostname: str
    host_dir: Path
    root_helper: str | None
    home: Path


def _read_hostname(path: Path = Path("/etc/hostname")) -> str | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    host = "".join(ch for ch in raw if ch not in " \t\r\n")
    return host or None


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="setup-links.sh",
        add_help=True,
        description=(
            "Create or update symlinks from this repository to standard locations.\n"
            "- User-owned targets are linked directly.\n"
            "- Root-owned targets are skipped unless a root helper is provided."
        ),
    )
    p.add_argument("--host", help="Host directory name under hosts/ to use")
    p.add_argument(
        "--root-helper",
        help=(
            "Privilege helper used for root-owned targets (e.g. sudo, doas, 'sudo --'). "
            "When set, runs: ln -sfn SOURCE TARGET under the helper."
        ),
    )
    return p.parse_args(list(argv))


def compute_repo_root(script_path: Path) -> Path:
    return script_path.resolve().parent.parent


def compute_config(
    *,
    args: argparse.Namespace,
    script_path: Path,
    home: Path | None = None,
    hostname_path: Path = Path("/etc/hostname"),
) -> SetupConfig:
    repo_root = compute_repo_root(script_path)
    if home is None:
        home = Path.home()

    hostname = args.host or _read_hostname(hostname_path)
    if not hostname:
        raise ValueError("Host name is required and could not be inferred. Use --host.")

    host_dir = repo_root / "hosts" / hostname
    if not host_dir.is_dir():
        raise FileNotFoundError(f"Host directory not found: {host_dir}")

    root_helper = args.root_helper.strip() if args.root_helper else None
    if root_helper == "":
        root_helper = None

    return SetupConfig(
        repo_root=repo_root,
        hostname=hostname,
        host_dir=host_dir,
        root_helper=root_helper,
        home=home,
    )


def log_info(msg: str, *, out) -> None:
    print(f"[INFO] {msg}", file=out)


def log_warn(msg: str, *, err) -> None:
    print(f"[WARN] {msg}", file=err)


def log_error(msg: str, *, err) -> None:
    print(f"[ERROR] {msg}", file=err)


def ensure_parent_dir(target: Path, *, out) -> None:
    parent = target.parent
    if not parent.is_dir():
        log_info(f"Creating directory {parent}", out=out)
        parent.mkdir(parents=True, exist_ok=True)


def nearest_existing_path(path: Path) -> Path:
    cur = path
    while not cur.exists() and cur != cur.parent:
        cur = cur.parent
    return cur


def owner_uid_for_path(path: Path) -> int:
    existing = nearest_existing_path(path)
    return existing.stat().st_uid


def is_already_linked(target: Path, source: Path) -> bool:
    if not target.is_symlink():
        return False
    try:
        resolved = target.resolve(strict=False)
    except OSError:
        return False
    return resolved == source


def link_user_owned(source: Path, target: Path, *, out, err) -> None:
    ensure_parent_dir(target, out=out)

    if target.is_symlink():
        if is_already_linked(target, source):
            log_info(f"Already linked: {target} -> {source}", out=out)
            return
        log_info(f"Updating symlink: {target} -> {source}", out=out)
    elif target.exists():
        log_warn(f"Replacing existing path at {target} with symlink to {source}", err=err)
    else:
        log_info(f"Linking {target} -> {source}", out=out)

    # ln -sfn
    if target.exists() or target.is_symlink():
        try:
            target.unlink()
        except IsADirectoryError:
            # If it's a directory, replace it like `ln -sfn` would: remove and link.
            # Keep behavior explicit: caller should avoid replacing real dirs when possible.
            import shutil

            shutil.rmtree(target)
    target.symlink_to(source)


def build_root_helper_argv(root_helper: str, *, source: Path, target: Path) -> list[str]:
    """Build argv for privileged link creation.

    Matches bash behavior:
    - root_helper == 'sudo' -> ['sudo','ln','-sfn',SRC,TGT]
    - root_helper == 'doas' -> ['doas','ln','-sfn',SRC,TGT]
    - otherwise: split on whitespace and append ln invocation.
    """

    if root_helper == "sudo":
        return ["sudo", "ln", "-sfn", str(source), str(target)]
    if root_helper == "doas":
        return ["doas", "ln", "-sfn", str(source), str(target)]

    parts = root_helper.split()
    return [*parts, "ln", "-sfn", str(source), str(target)]


def process_mapping(
    mapping: LinkMapping,
    *,
    root_helper: str | None,
    runner: RootCommandRunner,
    out,
    err,
) -> int:
    source, target = mapping.source, mapping.target

    if not source.exists():
        log_warn(f"Source does not exist, skipping: {source}", err=err)
        return 0

    owner_uid = owner_uid_for_path(target)
    if owner_uid == 0:
        if root_helper:
            log_info(f"Delegating root-owned target to helper: {target}", out=out)
            argv = build_root_helper_argv(root_helper, source=source, target=target)
            return runner.run(argv)
        log_warn(f"Skipping root-owned target: {target}", err=err)
        log_warn(f"To link manually, run (as root): ln -sfn {source} {target}", err=err)
        return 0

    link_user_owned(source, target, out=out, err=err)
    return 0


def compute_mappings(cfg: SetupConfig) -> list[LinkMapping]:
    mappings: list[LinkMapping] = []
    host_dir = cfg.host_dir
    home = cfg.home

    # Home Manager config
    if (host_dir / "home.nix").is_file():
        mappings.append(
            LinkMapping(
                source=host_dir / "home.nix",
                target=home / ".config" / "home-manager" / "home.nix",
            )
        )
    if (host_dir / "home").is_dir():
        mappings.append(
            LinkMapping(source=host_dir / "home", target=home / ".config" / "home-manager")
        )

    # NixOS system files
    if (host_dir / "configuration.nix").is_file():
        mappings.append(
            LinkMapping(
                source=host_dir / "configuration.nix",
                target=Path("/etc/nixos/configuration.nix"),
            )
        )
    if (host_dir / "hardware-configuration.nix").is_file():
        mappings.append(
            LinkMapping(
                source=host_dir / "hardware-configuration.nix",
                target=Path("/etc/nixos/hardware-configuration.nix"),
            )
        )

    # Scripts into ~/.local/bin
    user_bin_dir = home / ".local" / "bin"
    scripts_dir = cfg.repo_root / "scripts"
    if scripts_dir.is_dir():
        for path in sorted(scripts_dir.iterdir()):
            if path.is_file() and os.access(path, os.X_OK):
                mappings.append(LinkMapping(source=path, target=user_bin_dir / path.name))

    # Dotfiles: dotfiles/home/* -> ~/.<name>
    dotfiles_home = cfg.repo_root / "dotfiles" / "home"
    if dotfiles_home.is_dir():
        for path in sorted(dotfiles_home.iterdir()):
            mappings.append(LinkMapping(source=path, target=home / f".{path.name}"))

    return mappings


def main(argv: Sequence[str] | None = None, *, runner: RootCommandRunner | None = None, out=None, err=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if out is None:
        out = sys.stdout
    if err is None:
        err = sys.stderr
    if runner is None:
        runner = SubprocessRunner()

    try:
        args = parse_args(argv)
        cfg = compute_config(args=args, script_path=Path(__file__))
    except SystemExit:
        raise
    except Exception as e:
        log_error(str(e), err=err)
        return 1

    log_info(f"Using host configuration from {cfg.host_dir}", out=out)

    mappings = compute_mappings(cfg)
    if not mappings:
        log_warn("No mappings found to process.", err=err)
        return 0

    rc = 0
    for m in mappings:
        rc = max(rc, process_mapping(m, root_helper=cfg.root_helper, runner=runner, out=out, err=err))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

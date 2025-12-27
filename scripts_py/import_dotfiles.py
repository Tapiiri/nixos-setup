from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from scripts_py.utils import repo_root_from_script_path


@dataclass(frozen=True)
class ImportPaths:
    repo_root: Path
    dot_home: Path
    dot_config: Path
    home_dir: Path


def compute_paths(*, script_path: Path, home_dir: Path | None = None) -> ImportPaths:
    repo_root = repo_root_from_script_path(script_path)
    if home_dir is None:
        home_dir = Path.home()
    return ImportPaths(
        repo_root=repo_root,
        dot_home=repo_root / "dotfiles" / "home",
        dot_config=repo_root / "dotfiles" / "config",
        home_dir=home_dir,
    )


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="import-dotfiles",
        description=(
            "Import existing user config into this repo's dotfiles/ tree.\n"
            "This copies: ~/.<NAME> -> dotfiles/home/<NAME> and ~/.config/<NAME> -> "
            "dotfiles/config/<NAME>.\n\n"
            "Safety: won't overwrite existing files/dirs in dotfiles/."
        ),
    )
    p.add_argument(
        "--from-home",
        nargs="+",
        default=[],
        metavar="NAME",
        help="Copy ~/.<NAME> into dotfiles/home/<NAME>",
    )
    p.add_argument(
        "--from-config",
        nargs="+",
        default=[],
        metavar="NAME",
        help="Copy ~/.config/<NAME> into dotfiles/config/<NAME>",
    )
    return p.parse_args(list(argv))


def ensure_dirs(paths: ImportPaths) -> None:
    paths.dot_home.mkdir(parents=True, exist_ok=True)
    paths.dot_config.mkdir(parents=True, exist_ok=True)


def planned_imports(
    paths: ImportPaths,
    *,
    from_home: Iterable[str],
    from_config: Iterable[str],
) -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    for name in from_home:
        pairs.append((paths.home_dir / f".{name}", paths.dot_home / name))
    for name in from_config:
        pairs.append((paths.home_dir / ".config" / name, paths.dot_config / name))
    return pairs


def copy_one(src: Path, dst: Path, *, out, err) -> int:
    """Copy src -> dst preserving metadata, without overwriting.

    Returns 0 on success/skip, non-zero on copy failure.
    """

    if not src.exists() and not src.is_symlink():
        print(f"[WARN] Missing source, skipping: {src}", file=err)
        return 0
    if dst.exists() or dst.is_symlink():
        print(f"[SKIP] Already exists in repo: {dst}", file=err)
        return 0

    dst.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Mirror `cp -a` as closely as reasonable in Python:
        # - Preserve metadata (copy2)
        # - For directories, recurse
        if src.is_dir() and not src.is_symlink():
            shutil.copytree(src, dst, symlinks=True, copy_function=shutil.copy2)
        else:
            # copy2 follows symlinks by default; emulate cp -a by copying the link itself.
            if src.is_symlink():
                target = os.readlink(src)
                os.symlink(target, dst)
            else:
                shutil.copy2(src, dst)

        print(f"[OK] Imported {src} -> {dst}", file=out)
        return 0
    except OSError as e:
        print(f"[ERR] Failed to import {src} -> {dst}: {e}", file=err)
        return 1


def main(argv: Sequence[str] | None = None, *, out=None, err=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if out is None:
        out = sys.stdout
    if err is None:
        err = sys.stderr

    args = parse_args(argv)
    if not args.from_home and not args.from_config:
        # Keep bash UX: show help if no args.
        parse_args(["-h"])  # triggers SystemExit

    paths = compute_paths(script_path=Path(__file__))
    ensure_dirs(paths)

    rc = 0
    for src, dst in planned_imports(paths, from_home=args.from_home, from_config=args.from_config):
        rc = max(rc, copy_one(src, dst, out=out, err=err))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

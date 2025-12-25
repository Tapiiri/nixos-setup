from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol, Sequence


def log_info(msg: str, *, out) -> None:
    print(f"[INFO] {msg}", file=out)


def log_warn(msg: str, *, err) -> None:
    print(f"[WARN] {msg}", file=err)


def log_error(msg: str, *, err) -> None:
    print(f"[ERROR] {msg}", file=err)


# How far upwards we search when trying to locate the repo root.
FIND_UPWARDS_LIMIT = 8


class Runner(Protocol):
    def exec(self, argv: Sequence[str]) -> "NoReturn":  # pragma: no cover
        """Replace the current process with argv[0] and arguments."""


class OsExecRunner:
    def exec(self, argv: Sequence[str]) -> "NoReturn":
        os.execvp(argv[0], list(argv))
        raise AssertionError("os.execvp returned")


@dataclass(frozen=True)
class RepoMarkers:
    """Files/dirs that must exist for a directory to be considered the repo root."""

    files: tuple[str, ...] = ("flake.nix",)
    dirs: tuple[str, ...] = ("scripts_py",)


def _has_markers(path: Path, markers: RepoMarkers) -> bool:
    return all((path / f).is_file() for f in markers.files) and all(
        (path / d).is_dir() for d in markers.dirs
    )


def find_upwards(start: Path, *, markers: RepoMarkers) -> Path | None:
    """Walk upwards from start until we find a directory that matches markers."""

    cur = start.resolve()
    for _ in range(FIND_UPWARDS_LIMIT):
        if _has_markers(cur, markers):
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def bootstrap_repo_import_path(
    *,
    script_file: str | Path,
    markers: RepoMarkers,
    extra_candidates: Iterable[Path] = (),
) -> Path | None:
    """Ensure repo root is on sys.path so `import scripts_py.*` works.

    This is intended for small executable entrypoints under `scripts/` that may
    be symlinked into ~/.local/bin.

    Returns the detected repo root if found.
    """

    exe = Path(script_file).resolve()
    candidates = [exe.parent.parent, exe.parent, exe, *list(extra_candidates)]

    repo_root: Path | None = None
    for c in candidates:
        repo_root = find_upwards(c, markers=markers) or repo_root
        if repo_root:
            break

    if repo_root and str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    return repo_root


def repo_root_from_script_path(
    script_path: Path,
    *,
    markers: RepoMarkers = RepoMarkers(),
) -> Path:
    """Determine the repo root for an implementation module.

    Our convention:
    - implementation modules live under <repo>/scripts_py/*.py
    - wrappers live under <repo>/scripts/*

    So the fast path is script_path.parent.parent. We still validate using
    markers, and fall back to a marker-based upward search to handle odd
    installs/copies.
    """

    script_path = script_path.resolve()
    candidates = [script_path.parent.parent, script_path.parent]
    for c in candidates:
        root = find_upwards(c, markers=markers)
        if root:
            return root

    root = find_upwards(script_path, markers=markers)
    if root:
        return root

    raise FileNotFoundError(
        f"Could not locate repo root from {script_path} (expected markers: {markers})."
    )


def read_hostname(path: Path = Path("/etc/hostname")) -> str | None:
    """Read hostname from a file, trimming whitespace.

    Returns None if the file can't be read or results in an empty hostname.
    """

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    host = "".join(ch for ch in raw if ch not in " \t\r\n")
    return host or None

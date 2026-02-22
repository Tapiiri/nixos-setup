from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# How far upwards we search when trying to locate the repo root.
FIND_UPWARDS_LIMIT = 8


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
    for candidate in candidates:
        repo_root = find_upwards(candidate, markers=markers) or repo_root
        if repo_root:
            break

    if repo_root and str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    return repo_root


def repo_root_from_script_path(
    script_path: Path,
    *,
    markers: RepoMarkers | None = None,
) -> Path:
    """Determine the repo root for an implementation module.

    Our convention:
    - implementation modules live under <repo>/scripts_py/**
    - wrappers live under <repo>/scripts/*

    We validate using markers and fall back to a marker-based upward search.
    This is intentionally tolerant of nested modules (e.g. scripts_py/cli/*).
    """

    script_path = script_path.resolve()
    if markers is None:
        markers = RepoMarkers()

    # Start from the containing directory, then walk upwards.
    root = find_upwards(script_path.parent, markers=markers)
    if root:
        return root

    # Last-resort: try starting from the file path itself.
    root2 = find_upwards(script_path, markers=markers)
    if root2:
        return root2

    raise FileNotFoundError(
        f"Could not locate repo root from {script_path} (expected markers: {markers})."
    )

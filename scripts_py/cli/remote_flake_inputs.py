"""List remote (non-path) flake inputs from flake.lock.

Reads the ``nodes.root.inputs`` map from flake.lock and filters out any
input whose ``original.type`` is ``"path"`` — these are local-only inputs
that don't exist on CI runners and must be skipped by ``nix flake update``.

Outputs the remaining input names, space-separated, to stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Sequence

from scripts_py.repo.context import repo_root_from_script_path


def get_remote_input_names(flake_lock_path: Path) -> list[str]:
    """Return sorted names of non-path inputs from flake.lock."""
    data = json.loads(flake_lock_path.read_text(encoding="utf-8"))
    nodes = data["nodes"]
    root_inputs = nodes["root"]["inputs"]

    remote: list[str] = []
    for name, key in root_inputs.items():
        node = nodes[key]
        input_type = node.get("original", {}).get("type", "path")
        if input_type != "path":
            remote.append(name)

    return sorted(remote)


def main(
    argv: Sequence[str] | None = None,
    *,
    repo_root: Path | None = None,
) -> int:
    """Print space-separated list of remote flake inputs."""
    if argv is None:
        argv = sys.argv[1:]

    if repo_root is None:
        try:
            repo_root = repo_root_from_script_path(Path(__file__))
        except FileNotFoundError as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 2

    flake_lock_path = repo_root / "flake.lock"

    try:
        names = get_remote_input_names(flake_lock_path)
    except (KeyError, json.JSONDecodeError, OSError) as exc:
        print(f"[ERROR] Could not parse {flake_lock_path}: {exc}", file=sys.stderr)
        return 2

    print(" ".join(names))
    return 0

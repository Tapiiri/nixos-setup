"""Compatibility shim for the historical import path.

The implementation now lives in scripts_py.cli.rebuild.
"""

from __future__ import annotations

from scripts_py.cli.rebuild import (
    DEFAULT_MIRROR_DIR,
    DEFAULT_SYSTEM_FLAKE_DIR,
    RebuildConfig,
    build_exec_command,
    build_nixos_rebuild_command,
    compute_config,
    ensure_mirror,
    main,
    mirror_fetch,
    mirror_push_from_dev,
    parse_args,
    root_ensure_etc_nixos_clone,
    root_set_origin_to_mirror,
    root_update_from_mirror,
    run_cp,
    sync_worktree,
)

__all__ = [
    "DEFAULT_MIRROR_DIR",
    "DEFAULT_SYSTEM_FLAKE_DIR",
    "RebuildConfig",
    "build_exec_command",
    "build_nixos_rebuild_command",
    "compute_config",
    "ensure_mirror",
    "main",
    "mirror_fetch",
    "mirror_push_from_dev",
    "parse_args",
    "root_ensure_etc_nixos_clone",
    "root_set_origin_to_mirror",
    "root_update_from_mirror",
    "run_cp",
    "sync_worktree",
]


if __name__ == "__main__":
    raise SystemExit(main())

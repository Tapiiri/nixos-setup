"""Compatibility facade.

Historically, many scripts imported helpers from scripts_py.utils.

These utilities are now split by intent:
- scripts_py.lib.utils: generic helpers (logging, runner, hostname)
- scripts_py.repo.context: repo-layout helpers (repo root detection, bootstrapping)

This module re-exports the original API to keep wrappers/tests stable.
"""

from __future__ import annotations

from scripts_py.lib.utils import OsExecRunner, Runner, log_error, log_info, log_warn, read_hostname
from scripts_py.repo.context import (
    FIND_UPWARDS_LIMIT,
    RepoMarkers,
    bootstrap_repo_import_path,
    find_upwards,
    repo_root_from_script_path,
)

__all__ = [
    "FIND_UPWARDS_LIMIT",
    "OsExecRunner",
    "RepoMarkers",
    "Runner",
    "bootstrap_repo_import_path",
    "find_upwards",
    "log_error",
    "log_info",
    "log_warn",
    "read_hostname",
    "repo_root_from_script_path",
]

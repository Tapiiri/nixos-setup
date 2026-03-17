"""CLI entrypoint for the tooling coverage audit.

Produces a coverage matrix showing which file types have linters, formatters,
and VS Code extensions configured.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts_py.lib.tooling_audit import (
    classify_files,
    compute_coverage,
    format_json,
    format_table,
    git_ls_files,
    load_registry,
)
from scripts_py.lib.tooling_discovery import discover_all
from scripts_py.lib.utils import log_error, log_info
from scripts_py.repo.context import repo_root_from_script_path


def audit(
    *,
    repo_root: Path,
    registry_path: Path,
    out,
    err,
    strict: bool = False,
    json_output: bool = False,
    no_discover: bool = False,
) -> int:
    """Run the tooling coverage audit.

    Returns 0 on success, 1 if --strict and unmuted gaps exist, 2 on error.
    """

    # Load registry.
    if not registry_path.is_file():
        log_error(f"Registry not found: {registry_path}", err=err)
        return 2

    specs = load_registry(registry_path)

    # Scan files.
    files = git_ls_files(repo_root)
    if not files:
        log_error("No files found (is this a git repository?)", err=err)
        return 2

    classified, unmapped = classify_files(files, specs, repo_root=repo_root)

    # Auto-discover tools.
    discovered = discover_all(repo_root) if not no_discover else []

    # Compute coverage.
    result = compute_coverage(specs, classified, unmapped, discovered=discovered)

    # Output.
    if json_output:
        out.write(format_json(result))
        out.write("\n")
    else:
        out.write(format_table(result))

    # Determine exit code.
    all_gaps = [g for rec in result.records for g in rec.gaps]
    unmuted_gaps = [g for g in all_gaps if not g.muted]

    if strict and unmuted_gaps:
        log_info(
            f"Strict mode: {len(unmuted_gaps)} unmuted gap(s) found — failing.",
            out=err,
        )
        return 1

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit tooling coverage for repo file types.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any file type has an unmuted gap.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output machine-readable JSON instead of a table.",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=None,
        help="Path to tooling-audit.toml (default: auto-detect in repo root).",
    )
    parser.add_argument(
        "--no-discover",
        action="store_true",
        help="Skip auto-discovery; use registry only.",
    )

    args = parser.parse_args(argv)

    repo_root = repo_root_from_script_path(Path(__file__))
    if repo_root is None:
        print("[ERROR] Could not locate repo root.", file=sys.stderr)
        return 2

    registry_path = args.registry or (repo_root / "tooling-audit.toml")

    return audit(
        repo_root=repo_root,
        registry_path=registry_path,
        out=sys.stdout,
        err=sys.stderr,
        strict=args.strict,
        json_output=args.json_output,
        no_discover=args.no_discover,
    )

"""Tooling coverage audit — core data model and logic.

Detects file types in the repository and evaluates whether each has linters,
formatters, and VS Code extensions configured.  Pure-logic module: no I/O
side-effects, no process spawning.
"""

from __future__ import annotations

import fnmatch
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Sequence, cast

import tomlkit

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

TOOL_CATEGORIES = ("linter", "formatter", "vscode_extension")


@dataclass(frozen=True)
class ToolEntry:
    """A single tool configured for a file type."""

    name: str
    source: str  # e.g. "devenv", "precommit", "vscode", "pyproject", "registry"
    category: str  # "linter" | "formatter" | "vscode_extension"


@dataclass(frozen=True)
class FileTypeSpec:
    """Describes a file type from the registry."""

    key: str
    extensions: tuple[str, ...]
    glob_patterns: tuple[str, ...]
    shebang_patterns: tuple[str, ...]
    linters: tuple[ToolEntry, ...]
    formatters: tuple[ToolEntry, ...]
    vscode_extensions: tuple[str, ...]
    muted: tuple[str, ...]


@dataclass(frozen=True)
class Gap:
    """A missing tool category for a file type."""

    file_type: str
    category: str
    muted: bool


@dataclass
class CoverageRecord:
    """Combined registry + discovery result for one file type."""

    file_type: str
    matched_files: list[str] = field(default_factory=list[str])
    linters: list[ToolEntry] = field(default_factory=list[ToolEntry])
    formatters: list[ToolEntry] = field(default_factory=list[ToolEntry])
    vscode_extensions: list[str] = field(default_factory=list[str])
    muted: list[str] = field(default_factory=list[str])
    gaps: list[Gap] = field(default_factory=list[Gap])


@dataclass
class AuditResult:
    """Full audit output."""

    records: list[CoverageRecord] = field(default_factory=list[CoverageRecord])
    unmapped_files: list[str] = field(default_factory=list[str])


# ---------------------------------------------------------------------------
# Registry loading
# ---------------------------------------------------------------------------


def load_registry(path: Path) -> list[FileTypeSpec]:
    """Parse a tooling-audit.toml into a list of FileTypeSpec."""

    raw = cast(dict[str, Any], tomlkit.loads(path.read_text(encoding="utf-8")))
    file_types: dict[str, Any] = raw.get("file_types", {})
    specs: list[FileTypeSpec] = []
    for key, block in file_types.items():
        linters_raw: Any = block.get("linters") or []
        linters = tuple(
            ToolEntry(name=e["name"], source=e.get("source", "registry"), category="linter")
            for e in linters_raw
        )
        formatters_raw: Any = block.get("formatters") or []
        formatters = tuple(
            ToolEntry(name=e["name"], source=e.get("source", "registry"), category="formatter")
            for e in formatters_raw
        )
        specs.append(
            FileTypeSpec(
                key=key,
                extensions=tuple(block.get("extensions") or []),
                glob_patterns=tuple(block.get("glob_patterns") or []),
                shebang_patterns=tuple(block.get("shebang_patterns") or []),
                linters=linters,
                formatters=formatters,
                vscode_extensions=tuple(block.get("vscode_extensions") or []),
                muted=tuple(block.get("muted") or []),
            )
        )
    return specs


# ---------------------------------------------------------------------------
# File scanning
# ---------------------------------------------------------------------------


def git_ls_files(repo_root: Path) -> list[str]:
    """Return repo-relative paths via ``git ls-files``."""

    proc = subprocess.run(
        ["git", "ls-files"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return []
    return [line for line in proc.stdout.splitlines() if line]


def _read_shebang(repo_root: Path, relpath: str) -> str | None:
    """Read the first line of a file and extract the shebang interpreter."""

    try:
        full = repo_root / relpath
        with open(full, "rb") as fh:
            first_line = fh.readline(256)
        if not first_line.startswith(b"#!"):
            return None
        decoded = first_line.decode("utf-8", errors="replace").strip()
        # e.g. "#!/usr/bin/env -S python3" → "python3"
        parts = decoded.lstrip("#!").split()
        if not parts:
            return None
        # If "env" is the binary, the interpreter is the last arg.
        if parts[-1] == "env":
            return None
        return parts[-1]
    except OSError:
        return None


def _match_file_to_spec(relpath: str, spec: FileTypeSpec, shebang: str | None) -> bool:
    """Check if a file matches this FileTypeSpec."""

    # Extension match — handle compound extensions like .sh.tpl
    for ext in spec.extensions:
        if relpath.endswith(ext):
            return True

    # Glob pattern match
    for pattern in spec.glob_patterns:
        # Use PurePosixPath.match for paths, fnmatch for simpler globs
        if "/" in pattern:
            if PurePosixPath(relpath).match(pattern):
                return True
        else:
            if fnmatch.fnmatch(PurePosixPath(relpath).name, pattern):
                return True

    # Shebang match for extensionless files
    if shebang and "." not in PurePosixPath(relpath).name:
        for sp in spec.shebang_patterns:
            if shebang.endswith(sp):
                return True

    return False


def classify_files(
    files: Sequence[str],
    specs: Sequence[FileTypeSpec],
    repo_root: Path | None = None,
) -> tuple[dict[str, list[str]], list[str]]:
    """Classify files into file types.

    Returns (mapping of spec.key → list of relative paths, unmapped files).
    Shebangs are only checked when *repo_root* is given.
    """

    classified: dict[str, list[str]] = {s.key: [] for s in specs}
    unmapped: list[str] = []

    for f in files:
        shebang: str | None = None
        if repo_root and "." not in PurePosixPath(f).name:
            shebang = _read_shebang(repo_root, f)

        matched = False
        for spec in specs:
            if _match_file_to_spec(f, spec, shebang):
                classified[spec.key].append(f)
                matched = True
                # Don't break — file can match multiple specs (e.g. yaml + GHA)
        if not matched:
            unmapped.append(f)

    return classified, unmapped


# ---------------------------------------------------------------------------
# Coverage computation
# ---------------------------------------------------------------------------


def compute_coverage(
    specs: Sequence[FileTypeSpec],
    classified: dict[str, list[str]],
    unmapped: list[str],
    discovered: Sequence[ToolEntry] | None = None,
) -> AuditResult:
    """Build the coverage matrix.

    *discovered* is an optional list of auto-discovered ToolEntry objects.
    They are merged into the relevant CoverageRecord based on matching
    the tool's file-type association.
    """

    # Index discovered tools by (file_type, category)
    disc_by_ft: dict[str, list[ToolEntry]] = {}
    for tool in discovered or []:
        disc_by_ft.setdefault(tool.source, []).append(tool)

    result = AuditResult(unmapped_files=list(unmapped))

    for spec in specs:
        files = classified.get(spec.key, [])
        rec = CoverageRecord(
            file_type=spec.key,
            matched_files=files,
            linters=list(spec.linters),
            formatters=list(spec.formatters),
            vscode_extensions=list(spec.vscode_extensions),
            muted=list(spec.muted),
        )

        # Merge discovered tools.
        for tool in discovered or []:
            if _discovered_tool_matches_spec(tool, spec):
                _merge_tool_into_record(tool, rec)

        # Detect gaps — only for file types that have matched files.
        if files:
            if not rec.linters:
                rec.gaps.append(Gap(spec.key, "linter", muted="linter" in spec.muted))
            if not rec.formatters:
                rec.gaps.append(Gap(spec.key, "formatter", muted="formatter" in spec.muted))
            if not rec.vscode_extensions:
                rec.gaps.append(
                    Gap(spec.key, "vscode_extension", muted="vscode_extension" in spec.muted)
                )

        result.records.append(rec)

    return result


def _discovered_tool_matches_spec(tool: ToolEntry, spec: FileTypeSpec) -> bool:
    """Check if a discovered tool is relevant to a file type spec.

    Discovered tools carry their file-type key in the source field
    formatted as ``"<source>:<file_type>"``, e.g. ``"pyproject:python"``.
    """

    if ":" in tool.source:
        _, ft = tool.source.split(":", 1)
        return ft == spec.key
    return False


def _merge_tool_into_record(tool: ToolEntry, rec: CoverageRecord) -> None:
    """Add a discovered tool if not already present (by name)."""

    if tool.category == "linter":
        if not any(t.name == tool.name for t in rec.linters):
            rec.linters.append(tool)
    elif tool.category == "formatter":
        if not any(t.name == tool.name for t in rec.formatters):
            rec.formatters.append(tool)
    elif tool.category == "vscode_extension":
        if tool.name not in rec.vscode_extensions:
            rec.vscode_extensions.append(tool.name)


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

_CHECK = "\u2713"
_CROSS = "\u2717"
_MUTED = "\u2014"  # em-dash

# Category display labels
_CAT_LABELS = {
    "linter": "Linters",
    "formatter": "Formatters",
    "vscode_extension": "VS Code Extensions",
}


def format_table(result: AuditResult) -> str:
    """Render a human-readable ASCII table."""

    lines: list[str] = []

    # Header
    lines.append("")
    lines.append("Tooling Coverage Audit")
    lines.append("=" * 72)

    for rec in result.records:
        if not rec.matched_files:
            continue

        status_parts: list[str] = []
        for cat in TOOL_CATEGORIES:
            items = _get_category_items(rec, cat)
            if items:
                status_parts.append(f"{_CHECK} {_CAT_LABELS[cat]}: {', '.join(items)}")
            elif cat in rec.muted:
                status_parts.append(f"{_MUTED} {_CAT_LABELS[cat]}: (muted)")
            else:
                status_parts.append(f"{_CROSS} {_CAT_LABELS[cat]}: MISSING")

        lines.append("")
        lines.append(f"  {rec.file_type}  ({len(rec.matched_files)} files)")
        for part in status_parts:
            lines.append(f"    {part}")

    # Gaps summary
    all_gaps = [g for rec in result.records for g in rec.gaps]
    unmuted_gaps = [g for g in all_gaps if not g.muted]
    muted_gaps = [g for g in all_gaps if g.muted]

    lines.append("")
    lines.append("-" * 72)
    if unmuted_gaps:
        lines.append(f"  Gaps: {len(unmuted_gaps)} unmuted, {len(muted_gaps)} muted")
        for g in unmuted_gaps:
            lines.append(f"    {_CROSS} {g.file_type}: missing {g.category}")
    elif muted_gaps:
        lines.append(f"  No unmuted gaps ({len(muted_gaps)} muted)")
    else:
        lines.append("  Full coverage — no gaps detected")

    # Unmapped files
    if result.unmapped_files:
        lines.append("")
        lines.append(f"  Unmapped files ({len(result.unmapped_files)}):")
        for f in sorted(result.unmapped_files)[:20]:
            lines.append(f"    ? {f}")
        if len(result.unmapped_files) > 20:
            lines.append(f"    ... and {len(result.unmapped_files) - 20} more")

    lines.append("")
    return "\n".join(lines)


def _get_category_items(rec: CoverageRecord, category: str) -> list[str]:
    if category == "linter":
        return [t.name for t in rec.linters]
    elif category == "formatter":
        return [t.name for t in rec.formatters]
    elif category == "vscode_extension":
        return list(rec.vscode_extensions)
    return []


def format_json(result: AuditResult) -> str:
    """Render machine-readable JSON output."""

    data: dict[str, Any] = {
        "records": [],
        "unmapped_files": result.unmapped_files,
        "summary": {},
    }

    all_gaps: list[Gap] = []
    for rec in result.records:
        rec_data: dict[str, Any] = {
            "file_type": rec.file_type,
            "file_count": len(rec.matched_files),
            "linters": [{"name": t.name, "source": t.source} for t in rec.linters],
            "formatters": [{"name": t.name, "source": t.source} for t in rec.formatters],
            "vscode_extensions": list(rec.vscode_extensions),
            "muted": list(rec.muted),
            "gaps": [{"category": g.category, "muted": g.muted} for g in rec.gaps],
        }
        data["records"].append(rec_data)
        all_gaps.extend(rec.gaps)

    unmuted = [g for g in all_gaps if not g.muted]
    data["summary"] = {
        "total_gaps": len(all_gaps),
        "unmuted_gaps": len(unmuted),
        "muted_gaps": len(all_gaps) - len(unmuted),
        "unmapped_file_count": len(result.unmapped_files),
    }

    return json.dumps(data, indent=2)

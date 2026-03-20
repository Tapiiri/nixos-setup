"""Pluggable auto-discovery of development tools.

Each discovery source is a plain function that accepts a repo root and returns
a list of :class:`ToolEntry` objects.  The ``source`` field on each entry
uses the format ``"<origin>:<file_type_key>"`` so the audit engine can merge
discovered tools into the correct :class:`CoverageRecord`.

Adding a new source:
1.  Write ``discover_from_<name>(repo_root: Path) -> list[ToolEntry]``.
2.  Append it to :data:`DEFAULT_SOURCES`.

Everything here is pure-logic / file-reads only — no subprocess calls.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Sequence, cast

import tomlkit

from scripts_py.lib.tooling_audit import ToolEntry

# Type alias for a discovery function.
DiscoverySource = Callable[[Path], list[ToolEntry]]


# ---------------------------------------------------------------------------
# pyproject.toml
# ---------------------------------------------------------------------------


def discover_from_pyproject(repo_root: Path) -> list[ToolEntry]:
    """Detect tools configured in pyproject.toml."""

    pyproject = repo_root / "pyproject.toml"
    if not pyproject.is_file():
        return []

    raw = cast(dict[str, Any], tomlkit.loads(pyproject.read_text(encoding="utf-8")))
    tools: list[ToolEntry] = []

    # ruff
    if raw.get("tool", {}).get("ruff"):
        tools.append(ToolEntry(name="ruff", source="pyproject:python", category="linter"))

    # pytest
    if raw.get("tool", {}).get("pytest"):
        # Future-proof: test frameworks are not in v1 categories, but
        # we still detect them so they appear in discovery output.
        pass  # Will add when test_framework category is introduced.

    return tools


# ---------------------------------------------------------------------------
# VS Code Nix module (home/features/vscode/default.nix)
# ---------------------------------------------------------------------------

# Known extension ID → file type mappings.
_VSCODE_EXT_FILE_TYPE: dict[str, str] = {
    "jnoortheen.nix-ide": "nix",
    "davidanson.vscode-markdownlint": "markdown",
    "github.vscode-github-actions": "github-actions",
    "ms-python.python": "python",
    "charliermarsh.ruff": "python",
    "timonwong.shellcheck": "shell",
    "redhat.vscode-yaml": "yaml",
    "tamasfe.even-better-toml": "toml",
    "editorconfig.editorconfig": "_editorconfig",
    "mkhl.direnv": "_direnv",
    "github.copilot": "_ai",
    "github.vscode-pull-request-github": "_github",
}

# Regex to extract extension IDs from Nix expressions.
# Matches pkgs.vscode-extensions.<publisher>.<name>
_NIX_PKGS_EXT_RE = re.compile(r"pkgs\.vscode-extensions\.([a-zA-Z0-9_-]+)\.([a-zA-Z0-9_-]+)")
# Matches marketplace publisher/name in buildVscodeMarketplaceExtension blocks.
_NIX_MARKETPLACE_PUBLISHER_RE = re.compile(r'publisher\s*=\s*"([^"]+)"')
_NIX_MARKETPLACE_NAME_RE = re.compile(r'name\s*=\s*"([^"]+)"')


def discover_from_vscode_nix(repo_root: Path) -> list[ToolEntry]:
    """Extract VS Code extension IDs from the Nix module."""

    nix_file = repo_root / "home" / "features" / "vscode" / "default.nix"
    if not nix_file.is_file():
        return []

    content = nix_file.read_text(encoding="utf-8")
    ext_ids: set[str] = set()

    # 1. pkgs.vscode-extensions.<pub>.<name>
    for m in _NIX_PKGS_EXT_RE.finditer(content):
        publisher = m.group(1).replace("_", "-")
        name = m.group(2).replace("_", "-")
        ext_ids.add(f"{publisher}.{name}")

    # 2. buildVscodeMarketplaceExtension blocks – pair publisher + name
    # These appear in mktplcRef = { publisher = "…"; name = "…"; }
    blocks = re.findall(
        r"buildVscodeMarketplaceExtension\s*\{[^}]*mktplcRef\s*=\s*\{([^}]+)\}",
        content,
        re.DOTALL,
    )
    for block in blocks:
        pub_m = _NIX_MARKETPLACE_PUBLISHER_RE.search(block)
        name_m = _NIX_MARKETPLACE_NAME_RE.search(block)
        if pub_m and name_m:
            ext_ids.add(f"{pub_m.group(1)}.{name_m.group(1)}")

    # Convert to ToolEntry objects.
    tools: list[ToolEntry] = []
    for ext_id in sorted(ext_ids):
        ft = _VSCODE_EXT_FILE_TYPE.get(ext_id)
        if ft and not ft.startswith("_"):
            tools.append(
                ToolEntry(
                    name=ext_id,
                    source=f"vscode-nix:{ft}",
                    category="vscode_extension",
                )
            )

    return tools


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

DEFAULT_SOURCES: list[DiscoverySource] = [
    discover_from_pyproject,
    discover_from_vscode_nix,
]


def discover_all(
    repo_root: Path,
    sources: Sequence[DiscoverySource] | None = None,
) -> list[ToolEntry]:
    """Run all discovery sources and return a merged, deduplicated list."""

    if sources is None:
        sources = DEFAULT_SOURCES

    all_tools: list[ToolEntry] = []
    seen: set[tuple[str, str, str]] = set()

    for source_fn in sources:
        for tool in source_fn(repo_root):
            key = (tool.name, tool.category, tool.source)
            if key not in seen:
                seen.add(key)
                all_tools.append(tool)

    return all_tools

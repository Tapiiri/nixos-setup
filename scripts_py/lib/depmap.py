"""AST-based Python import dependency graph.

Builds a map from source files to their transitive internal dependencies,
enabling targeted test selection when files change.

Only resolves imports within the ``scripts_py`` and ``tests`` packages;
stdlib and third-party imports are silently ignored.
"""

from __future__ import annotations

import ast
from pathlib import Path

# Config files whose content affects all tests (e.g. pytest options, Python
# version bump).  Changes to any of these invalidate every attestation.
GLOBAL_CONFIG_FILES: tuple[str, ...] = ("pyproject.toml", "devenv.nix")

# Top-level packages that live inside the repo root.
_INTERNAL_PACKAGES: frozenset[str] = frozenset({"scripts_py", "tests"})


# ------------------------------------------------------------------
# Import extraction
# ------------------------------------------------------------------


def parse_imports(source: str) -> set[str]:
    """Return dotted module names for all ``import`` / ``from … import`` in *source*."""

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
    return names


# ------------------------------------------------------------------
# Module → file resolution
# ------------------------------------------------------------------


def resolve_to_repo_path(module_name: str, repo_root: Path) -> Path | None:
    """Map a dotted module name to a repo-relative ``.py`` file path.

    Returns ``None`` for modules outside ``_INTERNAL_PACKAGES``.
    """

    top = module_name.split(".")[0]
    if top not in _INTERNAL_PACKAGES:
        return None

    parts = module_name.split(".")
    # Try as a direct .py file first  (scripts_py.cli.rebuild → scripts_py/cli/rebuild.py)
    candidate = repo_root / Path(*parts).with_suffix(".py")
    if candidate.is_file():
        return candidate

    # Try as a package __init__.py  (scripts_py.cli → scripts_py/cli/__init__.py)
    candidate_pkg = repo_root / Path(*parts) / "__init__.py"
    if candidate_pkg.is_file():
        return candidate_pkg

    return None


# ------------------------------------------------------------------
# Graph construction
# ------------------------------------------------------------------


def build_import_graph(repo_root: Path) -> dict[Path, set[Path]]:
    """Scan ``scripts_py/`` and ``tests/`` for ``.py`` files and build a direct-import graph.

    Returns a mapping from absolute ``.py`` file path to the set of absolute
    ``.py`` file paths it directly imports (within the repo only).
    """

    graph: dict[Path, set[Path]] = {}
    for pkg_dir_name in ("scripts_py", "tests"):
        pkg_dir = repo_root / pkg_dir_name
        if not pkg_dir.is_dir():
            continue
        for py_file in sorted(pkg_dir.rglob("*.py")):
            try:
                source = py_file.read_text(encoding="utf-8")
            except OSError:
                continue
            imports = parse_imports(source)
            deps: set[Path] = set()
            for mod in imports:
                resolved = resolve_to_repo_path(mod, repo_root)
                if resolved is not None and resolved != py_file:
                    deps.add(resolved)
            graph[py_file] = deps
    return graph


# ------------------------------------------------------------------
# Transitive closure
# ------------------------------------------------------------------


def transitive_deps(graph: dict[Path, set[Path]], file: Path) -> set[Path]:
    """Return the full transitive closure of *file*'s imports (not including itself)."""

    visited: set[Path] = set()
    stack: list[Path] = list(graph.get(file, set()))
    while stack:
        current = stack.pop()
        if current in visited or current == file:
            continue
        visited.add(current)
        stack.extend(graph.get(current, set()) - visited)
    return visited


def affected_tests(
    graph: dict[Path, set[Path]],
    changed_files: set[Path],
    *,
    tests_dir_name: str = "tests",
) -> set[Path]:
    """Given a set of changed source files, return which test files need to run.

    A test file is considered affected if:
    - It is itself in *changed_files*, or
    - Any of its transitive dependencies is in *changed_files*.
    """

    test_files: set[Path] = set()
    for f in graph:
        # Only consider test files inside the tests directory.
        # Skip conftest.py — it's a pytest plugin, not a test module.
        if tests_dir_name not in f.parts:
            continue
        if f.name == "conftest.py":
            continue
        if f in changed_files:
            test_files.add(f)
            continue
        deps = transitive_deps(graph, f)
        if deps & changed_files:
            test_files.add(f)
    return test_files

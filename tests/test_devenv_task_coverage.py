"""Ensure pre-commit hooks cover every leaf task in the check:all tree.

The pre-push ``ci-check-all-attest`` hook writes a local attestation claiming
that ``check:all`` passed.  It trusts that the individual pre-commit hooks
already ran each leaf check.  This test validates that assumption by parsing
``devenv.nix`` and asserting parity between the two definitions.

If this test fails you most likely need to either:
  - add a pre-commit hook for a newly added leaf task, or
  - update HOOK_TASK_OVERRIDES below if the hook delegates differently.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_DEVENV_NIX = _REPO / "devenv.nix"

# Hooks that intentionally bypass ``devenv tasks run`` for a good reason
# (e.g. per-file filtering) but still cover the same domain as a task.
# Map: hook-id  →  task name it covers.
HOOK_TASK_OVERRIDES: dict[str, str] = {
    # Uses scripts/validate-schemastore-schemas directly (pass_filenames = true)
    # for incremental per-file validation.  The devenv task runs --all instead.
    # See the comment on the hook definition in devenv.nix.
    "schemastore-schemas": "lint:schemastore:validate",
    # Uses scripts/cached-pytest directly for file-level attestation caching.
    # Falls through to python -m pytest when attestations are stale/missing.
    "python-pytest": "tests:python:pytest",
}

# Hook IDs to exclude from coverage analysis entirely (not checks/lints).
_EXCLUDED_HOOKS: set[str] = {
    "ci-check-all-attest",  # pre-push attestation, not a check
}


def _read_devenv_nix() -> str:
    return _DEVENV_NIX.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Task-tree parsing
# ---------------------------------------------------------------------------


def _parse_task_after(src: str, task_name: str) -> list[str]:
    """Extract the ``after`` list for *task_name* from devenv.nix source."""
    pattern = rf'"{re.escape(task_name)}"\s*=\s*\{{[^}}]*?after\s*=\s*\[([^\]]*)\]'
    m = re.search(pattern, src, re.DOTALL)
    if not m:
        return []
    return re.findall(r'"([^"]+)"', m.group(1))


def _collect_leaf_tasks(src: str, root: str) -> set[str]:
    """Recursively resolve *after* deps; return tasks with no deps of their own."""
    deps = _parse_task_after(src, root)
    if not deps:
        return {root}
    leaves: set[str] = set()
    for dep in deps:
        leaves |= _collect_leaf_tasks(src, dep)
    return leaves


# ---------------------------------------------------------------------------
# Hook parsing
# ---------------------------------------------------------------------------


def _parse_hook_tasks(src: str) -> tuple[set[str], set[str]]:
    """Return (task_names_from_hooks, hook_ids_without_task).

    Scans ``git-hooks.hooks`` entries.  For each hook whose entry contains
    ``devenv tasks run <task>``, the task name is collected.  Hooks in
    ``_EXCLUDED_HOOKS`` are skipped entirely.

    The second set contains hook IDs that reference neither a devenv task nor
    an entry in ``HOOK_TASK_OVERRIDES`` — these are hooks that need review.
    """
    tasks: set[str] = set()
    unmapped_hooks: set[str] = set()

    # Match blocks like: hook-id = { ... entry = "..."; ... };
    # We iterate over hook blocks inside git-hooks.hooks.
    hook_block_re = re.compile(
        r"(\S+)\s*=\s*\{\s*"  # hook id
        r"(?:(?!\n\s{4}\};).)*?"  # non-greedy body
        r'entry\s*=\s*"([^"]+)"'  # entry value
        r"(?:(?!\n\s{4}\};).)*?"  # rest of body
        r"(?:"
        r"stages\s*=\s*\[([^\]]*)\]"  # optional stages
        r")?",
        re.DOTALL,
    )

    # Narrow to git-hooks.hooks block.
    hooks_section_re = re.compile(
        r"git-hooks\.hooks\s*=\s*\{(.*?)^\s{2}\};", re.DOTALL | re.MULTILINE
    )
    m = hooks_section_re.search(src)
    if not m:
        return tasks, unmapped_hooks
    hooks_body = m.group(1)

    for hm in hook_block_re.finditer(hooks_body):
        hook_id = hm.group(1).strip()
        entry = hm.group(2)

        if hook_id in _EXCLUDED_HOOKS:
            continue

        # Check for devenv task reference.
        task_match = re.search(r"devenv tasks run\s+([\w:]+)", entry)
        if task_match:
            tasks.add(task_match.group(1))
            continue

        # Check override map.
        if hook_id in HOOK_TASK_OVERRIDES:
            tasks.add(HOOK_TASK_OVERRIDES[hook_id])
            continue

        unmapped_hooks.add(hook_id)

    return tasks, unmapped_hooks


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDevenvTaskCoverage(unittest.TestCase):
    """Pre-commit hooks must cover every leaf task in check:all."""

    def test_check_all_leaves_covered_by_hooks(self) -> None:
        src = _read_devenv_nix()
        leaves = _collect_leaf_tasks(src, "check:all")
        hook_tasks, unmapped = _parse_hook_tasks(src)

        # Only consider hook tasks that are in the check:all tree.
        # Hooks for fmt:* tasks (e.g. alejandra-fmt → fmt:nix:alejandra) are
        # legitimate pre-commit hooks but outside check:all scope.
        extra_in_hooks = (hook_tasks - leaves) - {t for t in hook_tasks if t.startswith("fmt:")}

        missing = leaves - hook_tasks
        msgs: list[str] = []
        if missing:
            msgs.append(
                "Tasks in check:all tree but missing from pre-commit hooks: "
                f"{sorted(missing)}\n"
                "  → Add a hook in devenv.nix git-hooks.hooks, or add an entry "
                "to HOOK_TASK_OVERRIDES in this test."
            )
        if extra_in_hooks:
            msgs.append(
                "Pre-commit hooks reference check/lint/test tasks not in check:all tree: "
                f"{sorted(extra_in_hooks)}\n"
                "  → Either add the task to the appropriate aggregate (lint:all / tests:all) "
                "or remove the hook."
            )
        if unmapped:
            msgs.append(
                "Pre-commit hooks with no devenv task reference and no override mapping: "
                f"{sorted(unmapped)}\n"
                "  → Either switch the hook to 'devenv tasks run <task>' or add it to "
                "HOOK_TASK_OVERRIDES."
            )
        if msgs:
            self.fail("\n\n".join(msgs))

    def test_leaf_tasks_are_not_empty(self) -> None:
        """Sanity check: the parser actually finds leaf tasks."""
        src = _read_devenv_nix()
        leaves = _collect_leaf_tasks(src, "check:all")
        self.assertTrue(len(leaves) >= 5, f"Expected ≥5 leaf tasks, got {len(leaves)}: {leaves}")

    def test_hook_tasks_are_not_empty(self) -> None:
        """Sanity check: the parser actually finds hook task references."""
        src = _read_devenv_nix()
        hook_tasks, _ = _parse_hook_tasks(src)
        self.assertTrue(
            len(hook_tasks) >= 5, f"Expected ≥5 hook tasks, got {len(hook_tasks)}: {hook_tasks}"
        )


if __name__ == "__main__":
    unittest.main()

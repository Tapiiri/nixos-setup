"""Check that flake.lock is complete w.r.t. flake.nix inputs.

Parses input names from the ``inputs = { ... }`` block in flake.nix using
brace-depth tracking (no Nix evaluation) and verifies that every declared
input appears in the ``nodes.root.inputs`` map of flake.lock.

This catches the specific failure mode where a new input is added to
flake.nix but ``nix flake lock`` is forgotten before committing — a state
that evaluates fine locally but breaks remote evaluation via
``github:<owner>/<repo>`` because Nix cannot write the missing lock entries
back to a read-only GitHub tarball.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Sequence

from scripts_py.repo.context import repo_root_from_script_path


def _find_inputs_block(flake_nix: str) -> str | None:
    """Return the content of the top-level ``inputs = { ... }`` block."""
    m = re.search(r"\binputs\s*=\s*\{", flake_nix)
    if not m:
        return None

    pos = m.end()
    depth = 1
    chars: list[str] = []

    while pos < len(flake_nix) and depth > 0:
        c = flake_nix[pos]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        chars.append(c)
        pos += 1

    return "".join(chars)


def parse_flake_input_names(flake_nix: str) -> set[str]:
    """Extract top-level input names from a flake.nix string.

    Uses brace-depth tracking to distinguish top-level input declarations
    (e.g. ``nixpkgs.url = ...``, ``home-manager = { ... }``) from nested
    attributes such as ``inputs.nixpkgs.follows`` inside sub-blocks.
    Double-quoted strings are skipped so that URL values containing special
    characters cannot affect brace counting.
    """
    block = _find_inputs_block(flake_nix)
    if block is None:
        return set()

    names: set[str] = set()
    depth = 0
    i = 0

    while i < len(block):
        c = block[i]

        # Skip line comments.
        if c == "#":
            while i < len(block) and block[i] != "\n":
                i += 1
            continue

        # Skip double-quoted string literals (handles \-escapes).
        if c == '"':
            i += 1
            while i < len(block):
                if block[i] == "\\":
                    i += 2
                elif block[i] == '"':
                    i += 1
                    break
                else:
                    i += 1
            continue

        if c == "{":
            depth += 1
            i += 1
            continue

        if c == "}":
            depth -= 1
            i += 1
            continue

        if depth == 0:
            # At the top level of the inputs block: an identifier followed by
            # '.' (dotted form: foo.url = …) or '=' (block form: foo = { … })
            # is an input name.
            m = re.match(r"([\w][\w-]*)\s*[.=]", block[i:])
            if m:
                names.add(m.group(1))
                i += len(m.group(0))
                # Skip the rest of this top-level expression so nested
                # attribute names (e.g. "url" in "nixpkgs.url = …") are not
                # confused for input names.  Stop at '{' (block form: depth
                # tracking will handle it) or ';' (end of dotted/string form).
                while i < len(block):
                    c2 = block[i]
                    if c2 in ("{", ";"):
                        break
                    if c2 == '"':
                        i += 1
                        while i < len(block):
                            if block[i] == "\\":
                                i += 2
                            elif block[i] == '"':
                                i += 1
                                break
                            else:
                                i += 1
                    else:
                        i += 1
            else:
                i += 1
        else:
            i += 1

    return names


def get_locked_input_names(flake_lock_path: Path) -> set[str] | None:
    """Return the set of input names locked in flake.lock, or None on error."""
    try:
        data = json.loads(flake_lock_path.read_text(encoding="utf-8"))
        return set(data["nodes"]["root"]["inputs"].keys())
    except (KeyError, json.JSONDecodeError, OSError):
        return None


def check_lock_completeness(
    flake_nix: str,
    flake_lock_path: Path,
) -> tuple[bool, str]:
    """Return (ok, message) for the lock-completeness check."""
    declared = parse_flake_input_names(flake_nix)
    if not declared:
        return True, "flake.nix has no inputs block — nothing to check."

    locked = get_locked_input_names(flake_lock_path)
    if locked is None:
        return False, f"Could not parse {flake_lock_path} as JSON."

    missing = declared - locked
    if missing:
        return False, (
            f"flake.lock is missing lock entries for: {', '.join(sorted(missing))}\n"
            f"Run:  nix flake lock\n"
            f"Then stage flake.lock together with flake.nix."
        )

    return True, "flake.lock is consistent with flake.nix."


def main(
    argv: Sequence[str] | None = None,
    *,
    repo_root: Path | None = None,
) -> int:
    # argv is accepted for CLI symmetry but this script takes no arguments.
    if argv is None:
        argv = sys.argv[1:]

    if repo_root is None:
        try:
            repo_root = repo_root_from_script_path(Path(__file__))
        except FileNotFoundError as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 2

    flake_nix_path = repo_root / "flake.nix"
    flake_lock_path = repo_root / "flake.lock"

    try:
        flake_nix = flake_nix_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[ERROR] Could not read {flake_nix_path}: {exc}", file=sys.stderr)
        return 2

    ok, message = check_lock_completeness(flake_nix, flake_lock_path)
    if ok:
        print(message)
        return 0
    else:
        print(f"[FAIL] {message}", file=sys.stderr)
        return 1

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence, TextIO

from scripts_py.lib.utils import log_error, log_info
from scripts_py.repo.context import repo_root_from_script_path


@dataclass(frozen=True)
class LabelSpec:
    name: str
    color: str
    description: str


def _parse_simple_yaml_labels(text: str) -> list[LabelSpec]:
    """Parse our limited .github/labels.yml schema without external deps.

    Supported:
      labels:
        - name: "foo"
          color: "ffffff"
          description: "..."

    Notes:
    - Comments are allowed.
    - Only double-quoted or plain scalar values are supported.
    """

    # Strip comments, keep indentation.
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            continue
        # Remove inline comment only if it's preceded by whitespace.
        if "#" in line:
            before, _after = line.split("#", 1)
            if before.endswith(" ") or before.endswith("\t"):
                line = before.rstrip()
        if line.strip():
            lines.append(line)

    if not any(line.strip() == "labels:" for line in lines):
        raise ValueError("labels.yml must contain a top-level 'labels:' key")

    specs: list[LabelSpec] = []
    cur: dict[str, str] | None = None

    def flush() -> None:
        nonlocal cur
        if not cur:
            return
        missing = [k for k in ("name", "color", "description") if k not in cur]
        if missing:
            raise ValueError(f"Invalid label entry, missing {missing}: {cur}")
        specs.append(
            LabelSpec(
                name=cur["name"],
                color=normalize_color(cur["color"]),
                description=cur["description"],
            )
        )
        cur = None

    kv_re = re.compile(r"^\s{2,}([a-zA-Z0-9_-]+):\s*(.+?)\s*$")

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- "):
            # New item (may contain inline name: ...)
            flush()
            cur = {}
            rest = stripped[2:].strip()
            if rest:
                # e.g. - name: "dependencies"
                m = re.match(r"^([a-zA-Z0-9_-]+):\s*(.+?)\s*$", rest)
                if not m:
                    raise ValueError(f"Unsupported YAML line: {line}")
                cur[m.group(1)] = unquote(m.group(2))
            continue

        m = kv_re.match(line)
        if m and cur is not None:
            cur[m.group(1)] = unquote(m.group(2))
            continue

        # Ignore the top-level key and anything else we don't understand.
        if stripped == "labels:":
            continue

        raise ValueError(f"Unsupported YAML structure near: {line}")

    flush()
    # Ensure deterministic ordering (helps diffs in logs)
    specs.sort(key=lambda s: s.name.lower())
    return specs


def unquote(val: str) -> str:
    v = val.strip()
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        return v[1:-1]
    return v


def normalize_color(color: str) -> str:
    c = color.strip().lower()
    if c.startswith("#"):
        c = c[1:]
    if not re.fullmatch(r"[0-9a-f]{6}", c):
        raise ValueError(f"Invalid label color '{color}' (expected 6 hex digits)")
    return c


class Gh:
    def __init__(self, *, runner: Runner | None = None):
        self._runner = runner or SubprocessRunner()

    def api_json(self, args: Sequence[str]) -> Any:
        cp = self._runner.run_capture(["gh", "api", *args])
        if cp.returncode != 0:
            raise RuntimeError(
                f"gh api failed (exit {cp.returncode}):\n{cp.stderr.strip() or cp.stdout.strip()}"
            )
        return json.loads(cp.stdout or "null")

    def api_nooutput(self, args: Sequence[str]) -> None:
        cp = self._runner.run_capture(["gh", "api", *args])
        if cp.returncode != 0:
            raise RuntimeError(
                f"gh api failed (exit {cp.returncode}):\n{cp.stderr.strip() or cp.stdout.strip()}"
            )


@dataclass
class CompletedProcess:
    returncode: int
    stdout: str
    stderr: str


class Runner:
    def run_capture(self, argv: Sequence[str]) -> CompletedProcess:  # pragma: no cover
        raise NotImplementedError


class SubprocessRunner(Runner):
    def run_capture(self, argv: Sequence[str]) -> CompletedProcess:
        cp = subprocess.run(list(argv), text=True, capture_output=True)
        return CompletedProcess(int(cp.returncode), cp.stdout, cp.stderr)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog=Path(sys.argv[0]).name,
        description="Sync GitHub labels from .github/labels.yml using gh CLI.",
    )
    p.add_argument(
        "--repo",
        help="GitHub repo in OWNER/REPO form (defaults to gh's current repo)",
        default=None,
    )
    p.add_argument(
        "--file",
        help="Labels manifest path (default: <repo>/.github/labels.yml)",
        default=None,
    )
    p.add_argument(
        "--delete-unmanaged",
        action="store_true",
        help="Delete labels that are not listed in the manifest",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print intended changes but don't mutate GitHub",
    )
    return p.parse_args(list(argv))


def load_label_specs(path: Path) -> list[LabelSpec]:
    return _parse_simple_yaml_labels(path.read_text(encoding="utf-8"))


def fetch_existing_labels(gh: Gh, *, repo: str | None) -> dict[str, dict[str, Any]]:
    if repo:
        raw = gh.api_json([f"/repos/{repo}/labels", "--paginate"])
    else:
        raw = gh.api_json(["/repos/{owner}/{repo}/labels", "--paginate"])

    existing: dict[str, dict[str, Any]] = {}
    for item in raw:
        name = str(item.get("name", ""))
        if not name:
            continue
        existing[name] = {
            "name": name,
            "color": str(item.get("color", "")),
            "description": str(item.get("description") or ""),
        }
    return existing


def plan_changes(
    desired: Iterable[LabelSpec],
    existing: dict[str, dict[str, Any]],
    *,
    delete_unmanaged: bool,
) -> tuple[list[LabelSpec], list[LabelSpec], list[str]]:
    to_create: list[LabelSpec] = []
    to_update: list[LabelSpec] = []
    desired_by_name = {s.name: s for s in desired}

    for spec in desired_by_name.values():
        cur = existing.get(spec.name)
        if cur is None:
            to_create.append(spec)
            continue
        cur_color = normalize_color(cur.get("color", "")) if cur.get("color") else ""
        cur_desc = str(cur.get("description") or "")
        if cur_color != spec.color or cur_desc != spec.description:
            to_update.append(spec)

    to_delete: list[str] = []
    if delete_unmanaged:
        for name in existing.keys():
            if name not in desired_by_name:
                to_delete.append(name)

    to_create.sort(key=lambda s: s.name.lower())
    to_update.sort(key=lambda s: s.name.lower())
    to_delete.sort(key=lambda s: s.lower())
    return to_create, to_update, to_delete


def apply_changes(
    gh: Gh,
    *,
    repo: str | None,
    to_create: Sequence[LabelSpec],
    to_update: Sequence[LabelSpec],
    to_delete: Sequence[str],
    dry_run: bool,
    out: TextIO,
) -> None:
    def repo_args() -> list[str]:
        return [f"--repo={repo}"] if repo else []

    for s in to_create:
        log_info(f"Create label: {s.name}", out=out)
        if dry_run:
            continue
        gh.api_nooutput(
            [
                "-X",
                "POST",
                "/repos/{owner}/{repo}/labels",
                *repo_args(),
                "-f",
                f"name={s.name}",
                "-f",
                f"color={s.color}",
                "-f",
                f"description={s.description}",
            ]
        )

    for s in to_update:
        log_info(f"Update label: {s.name}", out=out)
        if dry_run:
            continue
        gh.api_nooutput(
            [
                "-X",
                "PATCH",
                f"/repos/{{owner}}/{{repo}}/labels/{s.name}",
                *repo_args(),
                "-f",
                f"new_name={s.name}",
                "-f",
                f"color={s.color}",
                "-f",
                f"description={s.description}",
            ]
        )

    for name in to_delete:
        log_info(f"Delete label: {name}", out=out)
        if dry_run:
            continue
        gh.api_nooutput(
            [
                "-X",
                "DELETE",
                f"/repos/{{owner}}/{{repo}}/labels/{name}",
                *repo_args(),
            ]
        )


def main(argv: Sequence[str] = ()) -> int:
    args = parse_args(argv)

    repo_root = repo_root_from_script_path(Path(__file__))
    manifest = Path(args.file) if args.file else (repo_root / ".github" / "labels.yml")
    if not manifest.is_file():
        log_error(f"Labels manifest not found: {manifest}", err=sys.stderr)
        return 2

    try:
        desired = load_label_specs(manifest)
    except Exception as e:
        log_error(f"Failed to parse {manifest}: {e}", err=sys.stderr)
        return 2

    gh = Gh()
    try:
        existing = fetch_existing_labels(gh, repo=args.repo)
    except Exception as e:
        log_error(f"Failed to fetch labels via gh: {e}", err=sys.stderr)
        return 2

    to_create, to_update, to_delete = plan_changes(
        desired, existing, delete_unmanaged=bool(args.delete_unmanaged)
    )

    if not to_create and not to_update and not to_delete:
        log_info("Labels already in sync.", out=sys.stdout)
        return 0

    for s in to_create:
        log_info(f"Will create: {s.name}", out=sys.stdout)
    for s in to_update:
        log_info(f"Will update: {s.name}", out=sys.stdout)
    for name in to_delete:
        log_info(f"Will delete: {name}", out=sys.stdout)

    try:
        apply_changes(
            gh,
            repo=args.repo,
            to_create=to_create,
            to_update=to_update,
            to_delete=to_delete,
            dry_run=bool(args.dry_run),
            out=sys.stdout,
        )
    except Exception as e:
        log_error(str(e), err=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))

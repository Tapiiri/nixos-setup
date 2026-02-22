from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

from scripts_py.lib.utils import log_error
from scripts_py.repo.context import repo_root_from_script_path


class CompletedProcess(Protocol):
    returncode: int
    stdout: str
    stderr: str


class Runner(Protocol):
    def run_capture(self, argv: Sequence[str]) -> CompletedProcess:
        raise NotImplementedError


@dataclass
class SimpleCompletedProcess:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class SubprocessRunner:
    def run_capture(self, argv: Sequence[str]) -> SimpleCompletedProcess:
        cp = subprocess.run(list(argv), text=True, capture_output=True)
        return SimpleCompletedProcess(int(cp.returncode), cp.stdout, cp.stderr)


@dataclass(frozen=True)
class Options:
    commit: str
    notes_ref: str
    task: str


DEFAULT_NOTES_REF = "refs/notes/nixos-setup-ci"


def parse_args(argv: Sequence[str]) -> Options:
    p = argparse.ArgumentParser(
        prog=Path(sys.argv[0]).name,
        description=(
            "Check whether a given commit has a successful local CI attestation stored as a git "
            "note. Prints 'true' or 'false' to stdout."
        ),
    )
    p.add_argument("--commit", default="HEAD", help="Commit-ish to check (default: HEAD)")
    p.add_argument(
        "--notes-ref",
        default=DEFAULT_NOTES_REF,
        help=f"git notes ref to read from (default: {DEFAULT_NOTES_REF})",
    )
    p.add_argument(
        "--task",
        default="check:all",
        help="Expected devenv task name in attestation (default: check:all)",
    )
    ns = p.parse_args(list(argv))
    return Options(commit=str(ns.commit), notes_ref=str(ns.notes_ref), task=str(ns.task))


def _git_rev_parse(commitish: str, *, runner: Runner) -> str:
    cp = runner.run_capture(["git", "rev-parse", commitish])
    if cp.returncode != 0:
        msg = cp.stderr.strip() or cp.stdout.strip() or f"git rev-parse {commitish} failed"
        raise RuntimeError(msg)
    return cp.stdout.strip()


def _git_note_show(*, ref: str, commit_sha: str, runner: Runner) -> str | None:
    cp = runner.run_capture(["git", "notes", "--ref", ref, "show", commit_sha])
    if cp.returncode != 0:
        return None
    note = cp.stdout.strip()
    return note or None


def _note_is_valid_attestation(note: str, *, expected_task: str) -> bool:
    note = note.strip()
    if not note:
        return False
    try:
        data = json.loads(note)
    except Exception:
        return False

    if not isinstance(data, dict):
        return False

    ok = data.get("ok") is True
    task = data.get("task")
    return ok and task == expected_task


def has_attestation(*, opts: Options, runner: Runner) -> bool:
    repo_root_from_script_path(Path(__file__))

    commit_sha = _git_rev_parse(opts.commit, runner=runner)
    note = _git_note_show(ref=opts.notes_ref, commit_sha=commit_sha, runner=runner)
    if note is None:
        return False
    return _note_is_valid_attestation(note, expected_task=opts.task)


def main(argv: Sequence[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    try:
        opts = parse_args(argv)
        res = has_attestation(opts=opts, runner=SubprocessRunner())
        sys.stdout.write("true" if res else "false")
        return 0
    except Exception as e:  # pragma: no cover - defensive
        log_error(str(e), err=sys.stderr)
        sys.stdout.write("false")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

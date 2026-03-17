from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, Sequence

from scripts_py.lib.utils import log_error, log_info, log_warn
from scripts_py.repo.context import repo_root_from_script_path


class CompletedProcess(Protocol):
    returncode: int
    stdout: str
    stderr: str


class Runner(Protocol):
    def run_capture(self, argv: Sequence[str]) -> CompletedProcess:
        raise NotImplementedError

    def run_check(self, argv: Sequence[str]) -> None:
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

    def run_check(self, argv: Sequence[str]) -> None:
        subprocess.run(list(argv), check=True)


@dataclass(frozen=True)
class Options:
    task: str
    notes_ref: str
    remote: str
    push: bool
    strict_push: bool
    commit: str
    run_task: bool


DEFAULT_NOTES_REF = "refs/notes/nixos-setup-ci"


def parse_args(argv: Sequence[str]) -> Options:
    p = argparse.ArgumentParser(
        prog=Path(sys.argv[0]).name,
        description=(
            "Run CI-equivalent checks locally and write a git-notes attestation "
            "that CI can read.\n\n"
            "This is intentionally opt-in and is mainly useful for personal repos where the same "
            "person runs checks locally and pushes to main."
        ),
    )
    p.add_argument(
        "--task",
        default="check:all",
        help="devenv task name to run (default: check:all)",
    )
    p.add_argument(
        "--notes-ref",
        default=DEFAULT_NOTES_REF,
        help=f"git notes ref to write to (default: {DEFAULT_NOTES_REF})",
    )
    p.add_argument(
        "--remote",
        default="origin",
        help="git remote to push notes to (default: origin)",
    )
    p.add_argument(
        "--push",
        action="store_true",
        help="Push the notes ref to the remote (uses git push --no-verify)",
    )
    p.add_argument(
        "--strict-push",
        action="store_true",
        help="Fail if pushing notes fails (default: best-effort)",
    )
    p.add_argument(
        "--commit",
        default="HEAD",
        help="Commit-ish to attest (default: HEAD)",
    )
    p.add_argument(
        "--no-run",
        action="store_true",
        help="Do not run the task; only write/push the attestation note",
    )

    ns = p.parse_args(list(argv))
    return Options(
        task=str(ns.task),
        notes_ref=str(ns.notes_ref),
        remote=str(ns.remote),
        push=bool(ns.push),
        strict_push=bool(ns.strict_push),
        commit=str(ns.commit),
        run_task=not bool(ns.no_run),
    )


def _git_rev_parse(commitish: str, *, runner: Runner) -> str:
    cp = runner.run_capture(["git", "rev-parse", commitish])
    if cp.returncode != 0:
        msg = cp.stderr.strip() or cp.stdout.strip() or f"git rev-parse {commitish} failed"
        raise RuntimeError(msg)
    return cp.stdout.strip()


def _maybe_devenv_version(*, runner: Runner) -> str | None:
    cp = runner.run_capture(["devenv", "version"])
    if cp.returncode != 0:
        return None
    out = cp.stdout.strip()
    return out or None


def _write_git_note(*, ref: str, commit_sha: str, message: str, runner: Runner) -> None:
    runner.run_check(["git", "notes", "--ref", ref, "add", "-f", "-m", message, commit_sha])


def _push_git_notes_ref(*, remote: str, ref: str, runner: Runner) -> None:
    # IMPORTANT: this is usually called from a git hook. Avoid infinite recursion by skipping hooks.
    runner.run_check(["git", "push", "--no-verify", remote, ref])


def _attestation_message(*, task: str, devenv_version: str | None) -> str:
    payload: dict[str, object] = {
        "schema": 1,
        "task": task,
        "ok": True,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if devenv_version is not None:
        payload["devenv"] = devenv_version
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def attest_ci_checks(*, opts: Options, runner: Runner, out, err) -> None:
    # Ensure we are in the repo (helps when scripts are invoked via symlinks).
    repo_root_from_script_path(Path(__file__))

    commit_sha = _git_rev_parse(opts.commit, runner=runner)

    if opts.run_task:
        log_info(f"Running devenv task: {opts.task}", out=out)
        runner.run_check(["devenv", "tasks", "run", "-m", "all", opts.task])

    devenv_version = _maybe_devenv_version(runner=runner)
    msg = _attestation_message(task=opts.task, devenv_version=devenv_version)

    log_info(f"Writing git note to {opts.notes_ref} for {commit_sha[:12]}...", out=out)
    _write_git_note(ref=opts.notes_ref, commit_sha=commit_sha, message=msg, runner=runner)

    if opts.push:
        log_info(f"Pushing notes ref to {opts.remote}...", out=out)
        try:
            _push_git_notes_ref(remote=opts.remote, ref=opts.notes_ref, runner=runner)
        except subprocess.CalledProcessError as e:
            if opts.strict_push:
                raise
            log_warn(f"Failed to push git notes (continuing): {e}", err=err)


def main(argv: Sequence[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    try:
        opts = parse_args(argv)
        attest_ci_checks(opts=opts, runner=SubprocessRunner(), out=sys.stdout, err=sys.stderr)
        log_info("✓ Local CI attestation written", out=sys.stdout)
        return 0
    except subprocess.CalledProcessError as e:
        log_error(f"Command failed: {e}", err=sys.stderr)
        return 2
    except Exception as e:  # pragma: no cover - defensive
        log_error(str(e), err=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

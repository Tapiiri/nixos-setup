from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, Sequence, TextIO

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
    verify_local: bool


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
    p.add_argument(
        "--verify-local",
        action="store_true",
        help=(
            "Before writing the attestation, verify that local attestation caches "
            "(nix check + test results) are fresh.  Used by the post-commit hook to "
            "ensure pre-commit hooks actually ran."
        ),
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
        verify_local=bool(ns.verify_local),
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


# ------------------------------------------------------------------
# Local attestation verification
# ------------------------------------------------------------------


def verify_local_attestations(
    repo_root: Path,
    *,
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> bool:
    """Check that local attestation caches prove all check:all checks passed.

    Returns ``True`` only when every registered CI check (nix-flake-check,
    pytest, ruff, pyright, yamllint, etc.) has a passing attestation whose
    input hash matches the current files.  Formatter-only checks (alejandra,
    shfmt, taplo fmt, jq fmt) are excluded because they live under
    ``fmt:all``, not ``check:all``.

    No age limit is enforced — the content hash already proves the
    attestation is still valid.  If files changed since the attestation
    was written the hash will differ and the lookup returns ``None``.

    This is used by the post-commit hook to decide whether writing a
    git-notes CI attestation is justified.  If pre-commit hooks were skipped
    (``git commit --no-verify``), these caches will be missing and this
    function returns ``False``, causing CI to run normally.
    """
    import math

    from scripts_py.lib.cached_check import CI_CHECKS, compute_input_hash
    from scripts_py.lib.cached_check import lookup as cc_lookup

    _out: TextIO = out if out is not None else sys.stdout
    _err: TextIO = err if err is not None else sys.stderr

    state_dir = repo_root / ".devenv" / "state"

    missing_checks: list[str] = []
    for check in CI_CHECKS:
        h = compute_input_hash(repo_root, globs=check.globs, files=check.files)
        result = cc_lookup(state_dir, check.name, h, max_age_s=math.inf)
        if result is not True:
            missing_checks.append(check.name)

    if missing_checks:
        log_warn(
            f"[verify-local] {len(missing_checks)} check(s) not attested: {missing_checks}",
            err=_err,
        )
        return False

    log_info(
        f"[verify-local] All {len(CI_CHECKS)} checks verified.",
        out=_out,
    )
    return True


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


def attest_ci_checks(*, opts: Options, runner: Runner, out: TextIO, err: TextIO) -> bool:
    """Run the attestation flow.  Returns ``True`` if a note was written."""
    # Ensure we are in the repo (helps when scripts are invoked via symlinks).
    repo_root = repo_root_from_script_path(Path(__file__))

    commit_sha = _git_rev_parse(opts.commit, runner=runner)

    if opts.verify_local:
        verified = verify_local_attestations(repo_root, out=out, err=err)
        if not verified and opts.run_task:
            # Auto-recovery: caches are stale (e.g. after a merge that changed
            # flake.lock, or a previous --no-verify commit).  Run check:all to
            # re-seed caches, then re-verify.
            log_info(
                "[attest-ci-checks] Local attestations stale — running "
                f"'{opts.task}' to re-seed caches before attesting.",
                out=out,
            )
            runner.run_check(["devenv", "tasks", "run", "-m", "all", opts.task])
            verified = verify_local_attestations(repo_root, out=out, err=err)
        if not verified:
            log_info(
                "[attest-ci-checks] Local attestations not verified "
                "— skipping CI attestation.  CI will run checks for this commit.",
                out=out,
            )
            return False
    elif opts.run_task:
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

    return True


def main(argv: Sequence[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    try:
        opts = parse_args(argv)
        wrote = attest_ci_checks(
            opts=opts, runner=SubprocessRunner(), out=sys.stdout, err=sys.stderr
        )
        if wrote:
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

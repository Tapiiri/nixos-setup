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

# Tighter max-age for --verify-local: attestations must be very recent
# (i.e. written during the pre-commit phase that just completed).
_VERIFY_LOCAL_MAX_AGE_S = 300.0  # 5 minutes


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
    max_age_s: float = _VERIFY_LOCAL_MAX_AGE_S,
    out=None,
    err=None,
) -> bool:
    """Check that local attestation caches prove all check:all checks passed recently.

    Returns ``True`` only when:

    1. The nix flake check attestation is fresh and passing for the current
       composite hash of all ``.nix`` files + ``flake.lock``.
    2. Every test file discovered in the import graph has a fresh passing
       attestation that matches its current content + dependency hashes.

    This is used by the post-commit hook to decide whether writing a
    git-notes CI attestation is justified.  If pre-commit hooks were skipped
    (``git commit --no-verify``), these caches will be stale or missing and
    this function returns ``False``, causing CI to run normally.
    """
    # Lazy imports to keep module loading lightweight.
    from scripts_py.lib.depmap import build_import_graph
    from scripts_py.lib.nix_check_attestation import compute_nix_hash, lookup_nix_attestation
    from scripts_py.lib.test_attestation import check_all_attested

    if out is None:
        out = sys.stdout
    if err is None:
        err = sys.stderr

    state_dir = repo_root / ".devenv" / "state"

    # 1. Verify nix flake check attestation.
    nix_hash = compute_nix_hash(repo_root)
    nix_result = lookup_nix_attestation(state_dir, nix_hash, max_age_s=max_age_s)
    if nix_result is not True:
        log_warn("[verify-local] Nix check attestation missing or stale.", err=err)
        return False

    # 2. Verify test attestations for ALL test files.
    graph = build_import_graph(repo_root)
    all_test_files = {
        f for f in graph if "tests" in f.parts and f.name.startswith("test_") and f.suffix == ".py"
    }

    if not all_test_files:
        log_warn("[verify-local] No test files found in import graph.", err=err)
        return False

    attested, unattested = check_all_attested(
        state_dir,
        all_test_files,
        graph,
        repo_root,
        max_age_s=max_age_s,
    )
    if unattested:
        names = sorted(str(f.relative_to(repo_root)) for f in unattested)
        log_warn(f"[verify-local] {len(unattested)} test(s) not attested: {names}", err=err)
        return False

    log_info(
        f"[verify-local] All checks verified (nix + {len(attested)} test file(s)).",
        out=out,
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


def attest_ci_checks(*, opts: Options, runner: Runner, out, err) -> bool:
    """Run the attestation flow.  Returns ``True`` if a note was written."""
    # Ensure we are in the repo (helps when scripts are invoked via symlinks).
    repo_root = repo_root_from_script_path(Path(__file__))

    commit_sha = _git_rev_parse(opts.commit, runner=runner)

    if opts.verify_local:
        if not verify_local_attestations(repo_root, out=out, err=err):
            log_info(
                "[attest-ci-checks] Local attestations not verified "
                "— skipping CI attestation.  CI will run checks for this commit.",
                out=out,
            )
            return False

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

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Protocol, Sequence

from scripts_py.ci.check_ci_attestation import Options as CheckOptions
from scripts_py.ci.check_ci_attestation import has_attestation
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
    commit: str
    only_on_event: str
    only_on_ref: str
    output_key: str
    github_output_path: Path | None
    verbose: bool


DEFAULT_NOTES_REF = "refs/notes/nixos-setup-ci"


def parse_args(argv: Sequence[str], *, env: Mapping[str, str] | None = None) -> Options:
    if env is None:
        import os as _os

        env = _os.environ
    p = argparse.ArgumentParser(
        prog=Path(sys.argv[0]).name,
        description=(
            "Decide whether CI can be skipped based on a local git-notes attestation and "
            "optionally write the decision to $GITHUB_OUTPUT (for GitHub Actions)."
        ),
    )
    p.add_argument(
        "--task",
        default="check:all",
        help="Expected devenv task name in attestation (default: check:all)",
    )
    p.add_argument(
        "--notes-ref",
        default=DEFAULT_NOTES_REF,
        help=f"git notes ref to read from (default: {DEFAULT_NOTES_REF})",
    )
    p.add_argument(
        "--remote",
        default="origin",
        help="Remote to fetch notes from (default: origin)",
    )
    p.add_argument("--commit", default=None, help="Commit SHA to check (default: $GITHUB_SHA)")

    p.add_argument(
        "--only-on-event",
        default="push",
        help="Only allow skipping on this GitHub event (default: push)",
    )
    p.add_argument(
        "--only-on-ref",
        default="refs/heads/main",
        help="Only allow skipping on this Git ref (default: refs/heads/main)",
    )

    p.add_argument(
        "--output-key",
        default="skip",
        help="Key written to $GITHUB_OUTPUT (default: skip)",
    )
    p.add_argument(
        "--github-output",
        default=None,
        help="Path to GitHub output file (default: $GITHUB_OUTPUT; use '-' to disable writing)",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Print informational logs to stdout/stderr (useful when running locally)",
    )

    ns = p.parse_args(list(argv))

    commit = ns.commit
    if commit is None:
        commit = env.get("GITHUB_SHA")

    github_output: Path | None
    if ns.github_output == "-":
        github_output = None
    elif ns.github_output:
        github_output = Path(ns.github_output)
    else:
        go = env.get("GITHUB_OUTPUT")
        github_output = Path(go) if go else None

    if not commit:
        raise ValueError("commit not provided and $GITHUB_SHA is not set")

    return Options(
        task=str(ns.task),
        notes_ref=str(ns.notes_ref),
        remote=str(ns.remote),
        commit=str(commit),
        only_on_event=str(ns.only_on_event),
        only_on_ref=str(ns.only_on_ref),
        output_key=str(ns.output_key),
        github_output_path=github_output,
        verbose=bool(ns.verbose),
    )


def should_consider_skipping(
    *,
    github_event_name: str | None,
    github_ref: str | None,
    allow_events: Sequence[str],
    allow_refs: Sequence[str],
) -> tuple[bool, str]:
    if github_event_name not in set(allow_events):
        return False, f"event '{github_event_name}' not allowed"
    if github_ref not in set(allow_refs):
        return False, f"ref '{github_ref}' not allowed"
    return True, "allowed"


def _fetch_notes_ref(*, remote: str, notes_ref: str, runner: Runner) -> None:
    # Notes are not fetched by default on GitHub Actions.
    runner.run_check(["git", "fetch", remote, f"{notes_ref}:{notes_ref}"])


def compute_skip(
    *,
    runner: Runner,
    task: str,
    notes_ref: str,
    remote: str,
    sha: str,
    github_event_name: str | None,
    github_ref: str | None,
    allow_events: Sequence[str] = ("push",),
    allow_refs: Sequence[str] = ("refs/heads/main",),
    verbose: bool = False,
    has_attestation_fn: Callable[..., bool] = has_attestation,
) -> bool:
    repo_root_from_script_path(Path(__file__))

    allowed, _reason = should_consider_skipping(
        github_event_name=github_event_name,
        github_ref=github_ref,
        allow_events=allow_events,
        allow_refs=allow_refs,
    )
    if not allowed:
        return False

    try:
        _fetch_notes_ref(remote=remote, notes_ref=notes_ref, runner=runner)
    except subprocess.CalledProcessError as e:
        # Best-effort: if we can't fetch notes, just don't skip.
        if verbose:
            log_warn(f"Failed to fetch notes ref (continuing): {e}", err=sys.stderr)
        return False

    return bool(
        has_attestation_fn(
            opts=CheckOptions(commit=sha, notes_ref=notes_ref, task=task),
            runner=runner,
        )
    )


def write_github_output(*, output_path: Path, key: str, value: str) -> None:
    _append_text(output_path, f"{key}={value}\n")


def _append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(text)


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    runner: Runner | None = None,
    compute_skip_fn: Callable[..., bool] = compute_skip,
    has_attestation_fn: Callable[..., bool] = has_attestation,
    print_fn: Callable[[str], object] | None = None,
) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if env is None:
        import os as _os

        env = dict(_os.environ)

    if runner is None:
        runner = SubprocessRunner()

    _print_fn = print_fn if print_fn is not None else sys.stdout.write

    try:
        opts = parse_args(argv, env=env)
        skip = compute_skip_fn(
            runner=runner,
            task=opts.task,
            notes_ref=opts.notes_ref,
            remote=opts.remote,
            sha=opts.commit,
            github_event_name=env.get("GITHUB_EVENT_NAME"),
            github_ref=env.get("GITHUB_REF"),
            allow_events=(opts.only_on_event,),
            allow_refs=(opts.only_on_ref,),
            verbose=opts.verbose,
            has_attestation_fn=has_attestation_fn,
        )
        out = "true" if skip else "false"

        if opts.verbose:
            log_info(f"skip={out}", out=sys.stdout)

        if opts.github_output_path is not None:
            write_github_output(output_path=opts.github_output_path, key=opts.output_key, value=out)
        else:
            _print_fn(out)
        return 0
    except Exception as e:  # pragma: no cover - defensive
        log_error(str(e), err=sys.stderr)
        # Default safe behavior: do not skip.
        go = env.get("GITHUB_OUTPUT")
        if go:
            write_github_output(output_path=Path(go), key="skip", value="false")
        else:
            _print_fn("false")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

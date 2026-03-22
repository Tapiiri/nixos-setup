"""Set up GitHub Pages for a repository using the ``gh`` CLI.

Enables GitHub Pages with the "GitHub Actions" build source so that a
deployment workflow (e.g. ``.github/workflows/docs.yml``) can publish
directly — no ``gh-pages`` branch required.

This script is idempotent: if Pages is already configured with the correct
source it reports the existing state and exits successfully.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence, TextIO, cast

from scripts_py.lib.utils import log_error, log_info

# ---------------------------------------------------------------------------
# Runner abstraction (for testability)
# ---------------------------------------------------------------------------


@dataclass
class CompletedProcess:
    returncode: int
    stdout: str
    stderr: str


class Runner:
    """Protocol-like base for subprocess execution — override in tests."""

    def run_capture(self, argv: Sequence[str]) -> CompletedProcess:  # pragma: no cover
        raise NotImplementedError


class SubprocessRunner(Runner):
    def run_capture(self, argv: Sequence[str]) -> CompletedProcess:
        cp = subprocess.run(list(argv), text=True, capture_output=True)
        return CompletedProcess(int(cp.returncode), cp.stdout, cp.stderr)


# ---------------------------------------------------------------------------
# GitHub API helper
# ---------------------------------------------------------------------------


class Gh:
    """Thin wrapper around ``gh api`` calls."""

    def __init__(self, *, runner: Runner | None = None) -> None:
        self._runner = runner or SubprocessRunner()

    def api_json(self, args: Sequence[str]) -> Any:
        cp = self._runner.run_capture(["gh", "api", *args])
        if cp.returncode != 0:
            raise RuntimeError(
                f"gh api failed (exit {cp.returncode}):\n{cp.stderr.strip() or cp.stdout.strip()}"
            )
        return json.loads(cp.stdout or "null")

    def api_json_nullable(self, args: Sequence[str]) -> tuple[int, Any]:
        """Like :meth:`api_json` but returns ``(status_code, body)`` without raising."""
        cp = self._runner.run_capture(["gh", "api", *args])
        body: Any = None
        if cp.stdout:
            try:
                body = json.loads(cp.stdout)
            except json.JSONDecodeError:
                body = cp.stdout.strip()
        return cp.returncode, body

    def api_nooutput(self, args: Sequence[str]) -> None:
        cp = self._runner.run_capture(["gh", "api", *args])
        if cp.returncode != 0:
            raise RuntimeError(
                f"gh api failed (exit {cp.returncode}):\n{cp.stderr.strip() or cp.stdout.strip()}"
            )

    def current_repo(self) -> str:
        """Return ``OWNER/REPO`` for the current working directory."""
        cp = self._runner.run_capture(
            ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]
        )
        if cp.returncode != 0:
            raise RuntimeError(f"Could not determine current repo via gh: {cp.stderr.strip()}")
        return cp.stdout.strip()


# ---------------------------------------------------------------------------
# Pages status types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PagesStatus:
    """Represents the current GitHub Pages state of a repo."""

    enabled: bool
    build_type: str  # "workflow" | "legacy" | "" (when disabled)
    url: str  # public URL, empty when disabled

    @classmethod
    def disabled(cls) -> PagesStatus:
        return cls(enabled=False, build_type="", url="")

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> PagesStatus:
        return cls(
            enabled=True,
            build_type=str(data.get("build_type", "legacy")),
            url=str(data.get("html_url", "")),
        )


# ---------------------------------------------------------------------------
# Pure logic
# ---------------------------------------------------------------------------


def check_pages_status(gh: Gh, repo: str) -> PagesStatus:
    """Query the current Pages configuration for *repo*."""
    rc, body = gh.api_json_nullable(
        [f"/repos/{repo}/pages", "--silent", "-H", "Accept: application/vnd.github+json"]
    )
    if rc != 0:
        # 404 means Pages is not enabled.
        if isinstance(body, dict):
            d = cast(dict[str, Any], body)
            if d.get("message") == "Not Found":
                return PagesStatus.disabled()
        # Also treat other non-zero as disabled (e.g. 403 → insufficient perms,
        # but we'll surface that at enable time with a better message).
        return PagesStatus.disabled()
    if isinstance(body, dict):
        return PagesStatus.from_api(cast(dict[str, Any], body))
    return PagesStatus.disabled()


@dataclass(frozen=True)
class PagesAction:
    """What the script intends to do."""

    kind: str  # "enable" | "noop" | "reconfigure"
    reason: str


def plan_pages_action(status: PagesStatus) -> PagesAction:
    """Decide what action to take based on the current *status*."""
    if not status.enabled:
        return PagesAction(kind="enable", reason="Pages is not enabled")
    if status.build_type == "workflow":
        return PagesAction(
            kind="noop",
            reason=f"Pages already configured with Actions source (url: {status.url})",
        )
    return PagesAction(
        kind="reconfigure",
        reason=f"Pages uses '{status.build_type}' source; switching to Actions workflow",
    )


# ---------------------------------------------------------------------------
# Side-effecting apply
# ---------------------------------------------------------------------------


def apply_pages_action(
    gh: Gh,
    repo: str,
    action: PagesAction,
    *,
    dry_run: bool,
    out: TextIO,
    err: TextIO,
) -> int:
    """Execute the planned action. Returns exit code."""
    if action.kind == "noop":
        log_info(action.reason, out=out)
        return 0

    log_info(action.reason, out=out)

    if dry_run:
        log_info(f"[dry-run] Would {action.kind} Pages on {repo}", out=out)
        return 0

    method = "POST" if action.kind == "enable" else "PUT"
    try:
        gh.api_nooutput(
            [
                "-X",
                method,
                f"/repos/{repo}/pages",
                "-H",
                "Accept: application/vnd.github+json",
                "-f",
                "build_type=workflow",
                # source.branch is required by the API even for workflow builds.
                "-f",
                "source[branch]=main",
            ]
        )
    except RuntimeError as exc:
        log_error(str(exc), err=err)
        return 1

    log_info(f"GitHub Pages enabled on {repo} (Actions workflow source).", out=out)
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog=Path(sys.argv[0]).name,
        description=(
            "Enable GitHub Pages with the 'GitHub Actions' build source.\n"
            "Idempotent: exits 0 if already correctly configured."
        ),
    )
    p.add_argument(
        "--repo",
        help="GitHub repo in OWNER/REPO form (defaults to gh's current repo)",
        default=None,
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print intended changes but don't mutate GitHub",
    )
    return p.parse_args(list(argv))


def main(argv: Sequence[str] = ()) -> int:
    args = parse_args(argv)
    out = sys.stdout
    err = sys.stderr

    gh = Gh()

    # Resolve repo
    repo: str
    if args.repo:
        repo = args.repo
    else:
        try:
            repo = gh.current_repo()
        except RuntimeError as exc:
            log_error(str(exc), err=err)
            return 2

    log_info(f"Checking GitHub Pages for {repo}...", out=out)

    try:
        status = check_pages_status(gh, repo)
    except Exception as exc:
        log_error(f"Failed to check Pages status: {exc}", err=err)
        return 2

    action = plan_pages_action(status)
    return apply_pages_action(gh, repo, action, dry_run=bool(args.dry_run), out=out, err=err)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))

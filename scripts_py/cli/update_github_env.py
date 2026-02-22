from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol, Sequence

from scripts_py.lib.utils import log_error, log_info, log_warn
from scripts_py.repo.context import repo_root_from_script_path


@dataclass(frozen=True)
class EnvLine:
    key: str
    value: str


_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def parse_env_text(text: str) -> list[EnvLine]:
    """Parse a simple .env file.

    Supported:
    - Empty lines and comment lines starting with #
    - KEY=VALUE (VALUE may be empty)

    Not supported (by design, to keep it predictable and dependency-free):
    - export KEY=VALUE
    - KEY: VALUE
    - multiline values
    - variable expansion
    - quoted values with escapes

    We keep this strict so failures are obvious and the script won't silently
    upload the wrong thing.
    """

    out: list[EnvLine] = []
    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue

        if "=" not in line:
            raise ValueError(f"Invalid .env line {i}: missing '='")

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid .env line {i}: empty key")
        if not _ENV_KEY_RE.fullmatch(key):
            raise ValueError(f"Invalid .env line {i}: invalid key '{key}'")

        # Preserve value exactly as written (minus surrounding whitespace).
        out.append(EnvLine(key=key, value=value.strip()))

    # Deterministic order is helpful in logs/tests.
    out.sort(key=lambda kv: kv.key)

    # De-duplicate: last occurrence wins (common env-file behavior).
    dedup: dict[str, EnvLine] = {}
    for kv in out:
        dedup[kv.key] = kv
    return [dedup[k] for k in sorted(dedup.keys())]


class CompletedProcess(Protocol):
    returncode: int
    stdout: str
    stderr: str


class Runner(Protocol):
    def run_capture(self, argv: Sequence[str], *, input: str | None = None) -> CompletedProcess:
        raise NotImplementedError


@dataclass
class SimpleCompletedProcess:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class SubprocessRunner:
    def run_capture(
        self, argv: Sequence[str], *, input: str | None = None
    ) -> SimpleCompletedProcess:
        import subprocess

        cp = subprocess.run(list(argv), text=True, capture_output=True, input=input)
        return SimpleCompletedProcess(int(cp.returncode), cp.stdout, cp.stderr)


class Gh:
    """Small wrapper around `gh` calls used by this tool.

    Split out so tests can assert exact argv and error handling.
    """

    def __init__(self, *, runner: Runner | None = None):
        self._runner = runner or SubprocessRunner()

    def _run_ok(self, argv: list[str], *, input: str | None = None) -> None:
        cp = self._runner.run_capture(argv, input=input)
        if cp.returncode != 0:
            msg = cp.stderr.strip() or cp.stdout.strip()
            raise RuntimeError(f"{' '.join(argv[:3])} failed (exit {cp.returncode}): {msg}")

    def environment_ensure(self, *, env: str, repo: str | None = None) -> None:
        """Ensure Actions environment exists.

        We do a GET first; if it 404s we create the environment.

        NOTE: GitHub's CLI/API supports environments via:
          GET  /repos/{owner}/{repo}/environments/{environment_name}
          PUT  /repos/{owner}/{repo}/environments/{environment_name}
        """

        repo_flag = ["--repo", repo] if repo else []

        # Check existence
        get_argv = [
            "gh",
            "api",
            "-H",
            "Accept: application/vnd.github+json",
            f"/repos/{{owner}}/{{repo}}/environments/{env}",
            *repo_flag,
        ]
        cp = self._runner.run_capture(get_argv)
        if cp.returncode == 0:
            return

        # `gh api` uses exit code 1 for most HTTP errors; detect 404 in output.
        combined = f"{cp.stderr}\n{cp.stdout}".lower()
        if "404" not in combined and "not found" not in combined:
            msg = cp.stderr.strip() or cp.stdout.strip()
            raise RuntimeError(f"gh api GET environment failed (exit {cp.returncode}): {msg}")

        # Create
        put_argv = [
            "gh",
            "api",
            "--method",
            "PUT",
            "-H",
            "Accept: application/vnd.github+json",
            f"/repos/{{owner}}/{{repo}}/environments/{env}",
            *repo_flag,
        ]
        self._run_ok(put_argv)

    def variable_set(self, *, name: str, env: str, body: str, repo: str | None = None) -> None:
        argv = ["gh", "variable", "set", name, "--env", env, "--body", body]
        if repo:
            argv += ["--repo", repo]
        self._run_ok(argv)

    def secret_set(self, *, name: str, env: str, value: str, repo: str | None = None) -> None:
        # Prefer stdin to avoid leaking in process listings.
        argv = ["gh", "secret", "set", name, "--env", env]
        if repo:
            argv += ["--repo", repo]
        self._run_ok(argv, input=value)


@dataclass(frozen=True)
class Options:
    environment: str
    env_file: Path
    secrets_file: Path | None
    repo: str | None
    dry_run: bool
    skip_missing: bool
    ensure_env: bool


def parse_args(argv: Sequence[str]) -> Options:
    p = argparse.ArgumentParser(
        prog=Path(sys.argv[0]).name,
        description=(
            "Update GitHub Actions environment variables and secrets from local files using "
            "gh CLI. "
            "Defaults: .env for variables and .env.secrets for secrets."
        ),
    )
    p.add_argument("environment", help="GitHub Actions environment name (e.g. production)")
    p.add_argument("--repo", default=None, help="Target repo in OWNER/REPO form (optional)")
    p.add_argument("--env-file", default=".env", help="Path to .env file (variables)")
    p.add_argument(
        "--secrets-file",
        default=".env.secrets",
        help="Path to secrets file (same KEY=VALUE format). Use '-' to disable.",
    )
    p.add_argument("--dry-run", action="store_true", help="Log intended actions without calling gh")
    p.add_argument(
        "--ensure-env",
        action="store_true",
        help="Create the GitHub Actions environment if it doesn't exist yet",
    )
    p.add_argument(
        "--skip-missing",
        action="store_true",
        help="Don't error if env/secrets files are missing; just warn",
    )

    ns = p.parse_args(list(argv))

    secrets_file: Path | None
    if ns.secrets_file == "-":
        secrets_file = None
    else:
        secrets_file = Path(ns.secrets_file)

    return Options(
        environment=str(ns.environment),
        env_file=Path(ns.env_file),
        secrets_file=secrets_file,
        repo=str(ns.repo) if ns.repo else None,
        dry_run=bool(ns.dry_run),
        skip_missing=bool(ns.skip_missing),
        ensure_env=bool(ns.ensure_env),
    )


def _load_env_file(path: Path) -> list[EnvLine]:
    return parse_env_text(path.read_text(encoding="utf-8"))


def _ensure_gh_present() -> None:
    # Keep it simple and portable.
    if not any(
        os.access(Path(p) / "gh", os.X_OK)
        for p in os.environ.get("PATH", "").split(os.pathsep)
        if p
    ):
        raise RuntimeError("GitHub CLI (gh) not found on PATH")


def update_from_pairs(
    *,
    gh: Gh,
    env: str,
    vars_pairs: Iterable[EnvLine],
    secrets_pairs: Iterable[EnvLine],
    repo: str | None,
    dry_run: bool,
    out,
) -> None:
    for kv in vars_pairs:
        log_info(f"Setting variable: {kv.key}", out=out)
        if not dry_run:
            gh.variable_set(name=kv.key, env=env, body=kv.value, repo=repo)

    for kv in secrets_pairs:
        log_info(f"Setting secret: {kv.key}", out=out)
        if not dry_run:
            gh.secret_set(name=kv.key, env=env, value=kv.value, repo=repo)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    try:
        repo_root_from_script_path(Path(__file__))
    except FileNotFoundError as e:
        log_error(str(e), err=sys.stderr)
        return 1

    try:
        opts = parse_args(argv)
        _ensure_gh_present()

        vars_pairs: list[EnvLine] = []
        secrets_pairs: list[EnvLine] = []

        if opts.env_file.exists():
            log_info(f"Loading variables from {opts.env_file}", out=sys.stdout)
            vars_pairs = _load_env_file(opts.env_file)
        else:
            msg = f"{opts.env_file} not found; skipping variables"
            if opts.skip_missing:
                log_warn(msg, err=sys.stderr)
            else:
                raise FileNotFoundError(msg)

        if opts.secrets_file is not None:
            if opts.secrets_file.exists():
                log_info(f"Loading secrets from {opts.secrets_file}", out=sys.stdout)
                secrets_pairs = _load_env_file(opts.secrets_file)
            else:
                msg = f"{opts.secrets_file} not found; skipping secrets"
                if opts.skip_missing:
                    log_warn(msg, err=sys.stderr)
                else:
                    raise FileNotFoundError(msg)

        log_info(
            f"Updating GitHub environment '{opts.environment}'"
            + (f" in repo {opts.repo}" if opts.repo else ""),
            out=sys.stdout,
        )

        gh = Gh()
        if opts.ensure_env:
            if opts.dry_run:
                log_info(
                    f"Would ensure environment exists: {opts.environment}",
                    out=sys.stdout,
                )
            else:
                gh.environment_ensure(env=opts.environment, repo=opts.repo)
        update_from_pairs(
            gh=gh,
            env=opts.environment,
            vars_pairs=vars_pairs,
            secrets_pairs=secrets_pairs,
            repo=opts.repo,
            dry_run=opts.dry_run,
            out=sys.stdout,
        )

        log_info("✓ Update complete", out=sys.stdout)
        return 0
    except Exception as e:
        log_error(str(e), err=sys.stderr)
        return 1

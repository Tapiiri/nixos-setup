from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from scripts_py.utils import log_error


@dataclass(frozen=True)
class DevshellChoice:
    flake_path: Path


def _is_path_arg(arg: str) -> bool:
    return not arg.startswith("-") and arg != "--"


def infer_start_dir(argv: Sequence[str], *, cwd: Path) -> Path:
    """Infer where the user is opening VS Code.

    We mimic the common `code <path>` usage:
    - first non-flag arg is treated as a path (dir or file)
    - if none exists, use cwd
    """

    workspace_arg: str | None = None
    for a in argv:
        if a == "--":
            break
        if _is_path_arg(a):
            workspace_arg = a
            break

    if not workspace_arg:
        return cwd

    p = Path(workspace_arg)
    if p.is_absolute():
        candidate = p
    else:
        candidate = cwd / p

    if candidate.is_dir():
        return candidate.resolve()
    return candidate.parent.resolve()


def walk_up(start: Path) -> Iterable[Path]:
    cur = start
    while True:
        yield cur
        if cur.parent == cur:
            return
        cur = cur.parent


def choose_devshell(start_dir: Path) -> DevshellChoice | None:
    for d in walk_up(start_dir):
        if (d / "dev" / "flake.nix").is_file():
            return DevshellChoice(flake_path=d / "dev")
        if (d / "flake.nix").is_file():
            return DevshellChoice(flake_path=d)
    return None


def which_all(program: str, *, env: dict[str, str] | None = None) -> list[Path]:
    """Return all matches for program on PATH, similar to `which -a`."""
    env2 = dict(os.environ)
    if env:
        env2.update(env)

    matches: list[Path] = []

    # Use `which -a` if present for correctness.
    which = shutil_which("which")
    if which:
        try:
            cp = subprocess.run(
                [which, "-a", program],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                env=env2,
            )
            for line in cp.stdout.splitlines():
                line = line.strip()
                if line:
                    matches.append(Path(line))
        except OSError:
            pass

    # Fallback: PATH scan
    if not matches:
        for part in env2.get("PATH", "").split(os.pathsep):
            if not part:
                continue
            cand = Path(part) / program
            if cand.exists() and os.access(cand, os.X_OK):
                matches.append(cand)

    # De-dupe while preserving order
    seen: set[Path] = set()
    out: list[Path] = []
    for m in matches:
        rp = m.resolve() if m.exists() else m
        if rp in seen:
            continue
        seen.add(rp)
        out.append(m)
    return out


def shutil_which(program: str) -> str | None:
    # local tiny which to avoid importing another module in tests
    for part in os.environ.get("PATH", "").split(os.pathsep):
        cand = Path(part) / program
        if cand.exists() and os.access(cand, os.X_OK):
            return str(cand)
    return None


def resolve_real_code(*, self_path: Path) -> Path | None:
    candidates = which_all("code")
    for c in candidates:
        try:
            if c.resolve() == self_path.resolve():
                continue
        except OSError:
            continue
        return c

    # If wrapper isn't installed as `code`, first `code` is OK.
    first = shutil_which("code")
    if first is None:
        return None
    p = Path(first)
    try:
        if p.resolve() == self_path.resolve():
            return None
    except OSError:
        return None
    return p


def build_exec_argv(
    *,
    real_code: Path,
    argv: Sequence[str],
    devshell: DevshellChoice | None,
) -> list[str]:
    if devshell is None:
        return [str(real_code), *argv]

    return [
        "nix",
        "develop",
        "--impure",
        str(devshell.flake_path),
        "-c",
        str(real_code),
        *argv,
    ]


def main(argv: Sequence[str] | None = None, *, cwd: Path | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if cwd is None:
        cwd = Path.cwd()

    self_path = Path(sys.argv[0]).resolve()
    real_code = resolve_real_code(self_path=self_path)
    if real_code is None:
        log_error("could not find the real 'code' binary on PATH", err=sys.stderr)
        return 127

    start_dir = infer_start_dir(argv, cwd=cwd)
    devshell = choose_devshell(start_dir)

    exec_argv = build_exec_argv(real_code=real_code, argv=argv, devshell=devshell)

    try:
        os.execvp(exec_argv[0], exec_argv)
    except OSError as e:
        log_error(str(e), err=sys.stderr)
        return 1

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Protocol, Sequence, TextIO

from scripts_py.lib.utils import log_error, log_info

NIX_CONF_PATH = Path("/etc/nix/nix.conf")
MARKER = "# Added by nixos-setup setup-wsl-nix"


class Runner(Protocol):
    def run(
        self,
        argv: Sequence[str],
        *,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess[str]: ...


class SubprocessRunner:
    def run(
        self,
        argv: Sequence[str],
        *,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            list(argv),
            check=False,
            text=True,
            capture_output=capture_output,
        )


def require_root() -> None:
    if os.geteuid() != 0:
        raise PermissionError("Run as root, for example: sudo setup-wsl-nix")


def default_user(*, env: dict[str, str] | None = None) -> str | None:
    if env is None:
        env = dict(os.environ)
    for key in ("SUDO_USER", "USER"):
        candidate = (env.get(key) or "").strip()
        if candidate and candidate != "root":
            return candidate
    return None


def ensure_trusted_user(
    user: str,
    conf_path: Path,
    *,
    out: TextIO,
) -> bool:
    """Idempotently add trusted-users to nix.conf. Returns True if changed."""
    try:
        current = conf_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        current = ""

    if MARKER in current:
        log_info(f"trusted-users already set in {conf_path}.", out=out)
        return False

    addition = f"\n{MARKER}\ntrusted-users = root {user}\n"
    conf_path.write_text(current + addition, encoding="utf-8")
    log_info(f"Added trusted-users = root {user} to {conf_path}.", out=out)
    return True


def restart_nix_daemon(
    runner: Runner,
    *,
    out: TextIO,
    err: TextIO,
) -> None:
    cp = runner.run(["systemctl", "restart", "nix-daemon"])
    if cp.returncode != 0:
        raise RuntimeError("Failed to restart nix-daemon.")
    log_info("nix-daemon restarted.", out=out)


def setup_wsl_nix(
    user: str,
    *,
    runner: Runner,
    out: TextIO,
    err: TextIO,
) -> int:
    require_root()
    changed = ensure_trusted_user(user, NIX_CONF_PATH, out=out)
    if changed:
        restart_nix_daemon(runner, out=out, err=err)
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: Runner | None = None,
    env: dict[str, str] | None = None,
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if runner is None:
        runner = SubprocessRunner()
    _out = out if out is not None else sys.stdout
    _err = err if err is not None else sys.stderr

    try:
        user = default_user(env=env)
        if not user:
            raise ValueError(
                "Could not determine the target user. Run via sudo or pass SUDO_USER."
            )
        return setup_wsl_nix(user, runner=runner, out=_out, err=_err)
    except SystemExit:
        raise
    except Exception as exc:
        log_error(str(exc), err=_err)
        return 1

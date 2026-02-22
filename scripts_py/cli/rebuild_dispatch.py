from __future__ import annotations

import argparse
import configparser
import os
import pty
import re
import select
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, NoReturn, Sequence

from scripts_py.cli.rebuild import DEFAULT_CONFIG_PATH, ENV_OFFLINE_OK


@dataclass(frozen=True)
class RunResult:
    returncode: int
    transcript: str


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    v = value.strip().lower()
    if not v:
        return None
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return None


def read_default_offline_ok(
    *,
    env: dict[str, str] | None = None,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> bool:
    if env is None:
        env = dict(os.environ)

    v = _parse_bool(env.get(ENV_OFFLINE_OK))
    if v is True:
        return True

    if not config_path.exists():
        return False

    cp = configparser.ConfigParser()
    try:
        cp.read(config_path, encoding="utf-8")
    except (OSError, configparser.Error):
        return False

    raw = None
    if cp.has_section("rebuild"):
        raw = cp.get("rebuild", "offline_ok", fallback=None)
    return bool(_parse_bool(raw))


def parse_dispatch_flags(argv: Sequence[str]) -> tuple[bool, bool]:
    want_dev = False
    offline_ok_cli = False

    for arg in argv:
        if arg == "--":
            break
        if arg == "--dev":
            want_dev = True
            continue
        if arg == "--offline-ok":
            offline_ok_cli = True
            continue

    return want_dev, offline_ok_cli


def is_online(*, timeout_s: float = 1.0) -> bool:
    # Keep this conservative and fast: if we can't resolve/connect to GitHub,
    # remote flake runs won't work.
    try:
        with socket.create_connection(("github.com", 443), timeout=timeout_s):
            return True
    except OSError:
        return False


_NETWORKISH_RE = re.compile(
    r"(failed to fetch|unable to download|could not resolve host(name)?|"
    r"temporary failure in name resolution|name or service not known|"
    r"network is unreachable|connection (timed out|refused|reset)|"
    r"ssh: could not resolve hostname|fatal: could not read from remote repository|"
    r"cache\.nixos\.org|github\.com|curl|http.*error|TLS|SSL)",
    re.IGNORECASE,
)


def is_networkish_failure(transcript: str) -> bool:
    return bool(_NETWORKISH_RE.search(transcript))


def run_with_pty(argv: Sequence[str]) -> RunResult:
    # Attach the child to a pty so it thinks it has a TTY (preserves colors and
    # interactive-ish output). We stream the output to our stdout and also keep
    # a transcript for heuristic fallback decisions.
    master_fd, slave_fd = pty.openpty()

    proc = subprocess.Popen(
        list(argv),
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
        text=False,
    )
    os.close(slave_fd)

    chunks: list[bytes] = []

    try:
        while True:
            rlist, _wlist, _xlist = select.select([master_fd], [], [], 0.1)
            if master_fd in rlist:
                try:
                    data = os.read(master_fd, 4096)
                except OSError:
                    data = b""
                if data:
                    os.write(sys.stdout.fileno(), data)
                    chunks.append(data)
                else:
                    break

            if proc.poll() is not None:
                # Drain remaining output.
                while True:
                    try:
                        data = os.read(master_fd, 4096)
                    except OSError:
                        data = b""
                    if not data:
                        break
                    os.write(sys.stdout.fileno(), data)
                    chunks.append(data)
                break

        rc = int(proc.wait())
    finally:
        try:
            os.close(master_fd)
        except OSError:
            pass

    transcript = b"".join(chunks).decode("utf-8", errors="replace")
    return RunResult(returncode=rc, transcript=transcript)


def _exec(argv: Sequence[str]) -> NoReturn:
    os.execvp(argv[0], list(argv))


def build_remote_cmd(argv: Sequence[str]) -> list[str]:
    return ["nix", "run", "github:Tapiiri/nixos-setup#rebuild-inner", "--", *argv]


def build_local_cmd(argv: Sequence[str]) -> list[str]:
    return ["nix", "run", "/etc/nixos#rebuild-inner", "--", *argv]


def parse_help_requested(argv: Sequence[str]) -> bool:
    for arg in argv:
        if arg == "--":
            return False
        if arg in ("-h", "--help"):
            return True
    return False


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="rebuild",
        add_help=True,
        formatter_class=argparse.RawTextHelpFormatter,
        description=(
            "Dispatcher for nixos-setup rebuild.\n\n"
            "Behavior:\n"
            "- When online: run the remote flake tool (github:Tapiiri/nixos-setup#rebuild-inner).\n"
            "- When offline and allowed: run the local tool (/etc/nixos#rebuild-inner).\n"
            "- With --dev: run rebuild-dev from your checkout.\n\n"
            "Most arguments are passed through to the inner rebuild tool.\n"
        ),
    )
    p.add_argument(
        "--dev",
        action="store_true",
        help="Use the local development wrapper (exec rebuild-dev)",
    )
    p.add_argument(
        "--offline-ok",
        action="store_true",
        help=(
            "Allow local-only operation when offline, and fallback to /etc/nixos "
            "on network-ish failures.\n"
            f"Can also be defaulted via {ENV_OFFLINE_OK} or {DEFAULT_CONFIG_PATH}."
        ),
    )
    return p


def main(
    argv: Sequence[str] | None = None,
    *,
    env: dict[str, str] | None = None,
    config_path: Path = DEFAULT_CONFIG_PATH,
    online_check: Callable[[], bool] = is_online,
    run_remote: Callable[[Sequence[str]], RunResult] = run_with_pty,
    exec_func: Callable[[Sequence[str]], NoReturn] = _exec,
) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if env is None:
        env = dict(os.environ)

    if parse_help_requested(argv):
        build_argparser().print_help(sys.stdout)
        return 0

    want_dev, offline_ok_cli = parse_dispatch_flags(argv)
    offline_ok = bool(offline_ok_cli) or read_default_offline_ok(env=env, config_path=config_path)

    if want_dev:
        exec_func(["rebuild-dev", *argv])

    if not online_check():
        if not offline_ok:
            print(
                "rebuild: offline, and offline mode is not enabled. Re-run with --offline-ok.",
                file=sys.stderr,
            )
            return 2
        exec_func(build_local_cmd(list(argv)))

    # Online: run remote tool first.
    remote_cmd = build_remote_cmd(list(argv))
    res = run_remote(remote_cmd)
    if res.returncode == 0:
        return 0

    if offline_ok and is_networkish_failure(res.transcript):
        print(
            "rebuild: remote run failed (network-ish); falling back to /etc/nixos",
            file=sys.stderr,
        )
        exec_func(build_local_cmd(list(argv)))

    return int(res.returncode)

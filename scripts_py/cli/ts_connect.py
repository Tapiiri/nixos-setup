from __future__ import annotations

import argparse
import sys
import time
from typing import Protocol, Sequence, TextIO


class SubprocessRunner(Protocol):
    def run(self, argv: Sequence[str]) -> int:  # pragma: no cover
        ...

    def run_output(self, argv: Sequence[str]) -> tuple[int, str]:  # pragma: no cover
        ...


class DefaultRunner:
    def run(self, argv: Sequence[str]) -> int:
        import subprocess

        return subprocess.run(list(argv)).returncode

    def run_output(self, argv: Sequence[str]) -> tuple[int, str]:
        import subprocess

        result = subprocess.run(list(argv), capture_output=True, text=True)
        return result.returncode, result.stdout


class Sleeper(Protocol):
    def __call__(self, seconds: float, /) -> None:  # pragma: no cover
        ...


DEFAULT_OP_ITEM_REF = "op://Development/tailscale-installer-authkey/credential"


def build_op_read_argv(item_ref: str) -> list[str]:
    return ["op", "read", item_ref]


def build_tailscale_up_argv(authkey: str, hostname: str) -> list[str]:
    return ["tailscale", "up", f"--authkey={authkey}", f"--hostname={hostname}"]


def build_tailscale_ip_argv() -> list[str]:
    return ["tailscale", "ip", "-4"]


def parse_tailscale_ip(output: str) -> str | None:
    """Extract the first non-empty line from tailscale ip output."""
    for line in output.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def fetch_authkey(
    item_ref: str,
    runner: SubprocessRunner,
    *,
    out: TextIO,
    err: TextIO,
) -> str | None:
    """Fetch the Tailscale auth key from 1Password via the op CLI.

    Returns the auth key string, or None on failure.
    """
    print("==> Fetching Tailscale auth key from 1Password...", file=out)
    rc, output = runner.run_output(build_op_read_argv(item_ref))
    if rc != 0:
        print(f"ERROR: op read exited with code {rc}", file=err)
        print("  Is OP_SERVICE_ACCOUNT_TOKEN set?", file=err)
        return None
    authkey = output.strip()
    if not authkey:
        print("ERROR: 1Password returned an empty auth key", file=err)
        return None
    return authkey


def connect(
    authkey: str,
    hostname: str,
    runner: SubprocessRunner,
    *,
    out: TextIO,
    err: TextIO,
    retries: int = 15,
    sleep: Sleeper = time.sleep,
) -> int:
    """Connect to Tailscale and print SSH connection info.

    Returns 0 on success, non-zero on failure.
    """
    print("==> Starting Tailscale...", file=out)
    rc = runner.run(build_tailscale_up_argv(authkey, hostname))
    if rc != 0:
        print(f"ERROR: tailscale up exited with code {rc}", file=err)
        return rc

    ts_ip: str | None = None
    for _ in range(retries):
        rc_ip, output = runner.run_output(build_tailscale_ip_argv())
        if rc_ip == 0:
            ts_ip = parse_tailscale_ip(output)
            if ts_ip is not None:
                break
        sleep(1)

    if ts_ip is None:
        print(f"ERROR: could not get Tailscale IP after {retries}s", file=err)
        return 1

    print("", file=out)
    print("==================================================", file=out)
    print("  Tailscale connected!", file=out)
    print("", file=out)
    print("  SSH from any machine on your tailnet:", file=out)
    print(f"    ssh root@{ts_ip}", file=out)
    print("", file=out)
    print("  Or by hostname:", file=out)
    print(f"    ssh root@{hostname}", file=out)
    print("==================================================", file=out)
    return 0


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="ts-connect",
        description=(
            "Fetch Tailscale auth key from 1Password and connect, "
            "enabling remote SSH access during NixOS install."
        ),
    )
    p.add_argument(
        "--item-ref",
        default=DEFAULT_OP_ITEM_REF,
        help=f"1Password item reference (default: {DEFAULT_OP_ITEM_REF})",
    )
    p.add_argument(
        "--hostname",
        default="nixos-installer",
        help="Tailscale hostname (default: nixos-installer)",
    )
    return p.parse_args(list(argv))


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: SubprocessRunner | None = None,
    out: TextIO | None = None,
    err: TextIO | None = None,
    sleep: Sleeper = time.sleep,
) -> int:
    _argv = argv if argv is not None else sys.argv[1:]
    _runner = runner if runner is not None else DefaultRunner()
    _out = out if out is not None else sys.stdout
    _err = err if err is not None else sys.stderr
    args = parse_args(_argv)
    authkey = fetch_authkey(args.item_ref, _runner, out=_out, err=_err)
    if authkey is None:
        return 1
    return connect(authkey, args.hostname, _runner, out=_out, err=_err, sleep=sleep)

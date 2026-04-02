from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence, TextIO

from scripts_py.lib.utils import log_error, log_info, log_warn

SSH_DROPIN_PATH = Path("/etc/ssh/sshd_config.d/10-tapiiri-wsl.conf")


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


@dataclass(frozen=True)
class SetupConfig:
    user: str
    tailscale_interface: str
    ssh_dropin_path: Path
    skip_ufw: bool
    allow_root_login: bool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="setup-wsl-ssh",
        description=(
            "Install and configure OpenSSH server on Ubuntu WSL for Dokploy-style "
            "deploy access over Tailscale."
        ),
    )
    parser.add_argument(
        "--user",
        help="Unix account allowed to log in over SSH (default: sudo user or current user)",
    )
    parser.add_argument(
        "--tailscale-interface",
        default="tailscale0",
        help="Network interface to use for the optional UFW rule (default: tailscale0)",
    )
    parser.add_argument(
        "--skip-ufw",
        action="store_true",
        help="Do not inspect or modify UFW rules",
    )
    parser.add_argument(
        "--allow-root-login",
        action="store_true",
        help="Allow root SSH login with keys only for tools like Dokploy",
    )
    return parser


def default_user(*, env: dict[str, str] | None = None) -> str | None:
    if env is None:
        env = dict(os.environ)

    for key in ("SUDO_USER", "USER"):
        candidate = (env.get(key) or "").strip()
        if candidate:
            return candidate

    return None


def compute_config(
    args: argparse.Namespace,
    *,
    env: dict[str, str] | None = None,
) -> SetupConfig:
    user = (args.user or default_user(env=env) or "").strip()
    if not user:
        raise ValueError("Could not determine SSH login user. Pass --user.")

    return SetupConfig(
        user=user,
        tailscale_interface=args.tailscale_interface,
        ssh_dropin_path=SSH_DROPIN_PATH,
        skip_ufw=bool(args.skip_ufw),
        allow_root_login=bool(args.allow_root_login),
    )


def render_sshd_dropin(user: str, *, allow_root_login: bool) -> str:
    allow_users = [user]
    permit_root_login = "no"
    if allow_root_login:
        permit_root_login = "prohibit-password"
        if "root" not in allow_users:
            allow_users.append("root")

    return (
        "# Managed by nixos-setup setup-wsl-ssh.\n"
        "PasswordAuthentication no\n"
        "KbdInteractiveAuthentication no\n"
        "ChallengeResponseAuthentication no\n"
        "PubkeyAuthentication yes\n"
        f"PermitRootLogin {permit_root_login}\n"
        f"AllowUsers {' '.join(allow_users)}\n"
    )


def require_root() -> None:
    if os.geteuid() != 0:
        raise PermissionError("Run as root, for example: sudo setup-wsl-ssh")


def run_checked(
    runner: Runner,
    argv: Sequence[str],
    *,
    err: TextIO,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    cp = runner.run(argv, capture_output=capture_output)
    if cp.returncode != 0:
        raise RuntimeError(
            f"Command failed ({cp.returncode}): {' '.join(argv)}\n"
            f"stdout:\n{cp.stdout or ''}\n"
            f"stderr:\n{cp.stderr or ''}"
        )
    return cp


def ensure_tailscale_running(runner: Runner, *, out: TextIO, err: TextIO) -> str | None:
    tailscale = shutil.which("tailscale")
    if not tailscale:
        raise FileNotFoundError(
            "tailscale CLI not found on PATH. Install it via Home Manager "
            "and ensure Tailscale is installed on the system."
        )

    status = run_checked(runner, [tailscale, "status", "--json"], err=err, capture_output=True)
    ip_result = runner.run([tailscale, "ip", "-4"], capture_output=True)
    ip = None
    if ip_result.returncode == 0:
        lines = [line.strip() for line in (ip_result.stdout or "").splitlines() if line.strip()]
        if lines:
            ip = lines[0]

    log_info("Verified that Tailscale is running.", out=out)
    if status.stdout:
        return ip
    return ip


def ensure_openssh_server_installed(runner: Runner, *, out: TextIO, err: TextIO) -> None:
    status = runner.run(["dpkg", "-s", "openssh-server"], capture_output=True)
    if status.returncode == 0:
        log_info("openssh-server is already installed.", out=out)
        return

    log_info("Installing openssh-server via apt-get.", out=out)
    run_checked(runner, ["apt-get", "update"], err=err)
    run_checked(runner, ["apt-get", "install", "-y", "openssh-server"], err=err)


def write_if_changed(path: Path, content: str, *, out: TextIO) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    current = None
    try:
        current = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        current = None

    if current == content:
        log_info(f"SSH config already up to date at {path}.", out=out)
        return False

    path.write_text(content, encoding="utf-8")
    log_info(f"Wrote SSH config to {path}.", out=out)
    return True


def validate_sshd_config(runner: Runner, *, err: TextIO) -> None:
    sshd = shutil.which("sshd") or "/usr/sbin/sshd"
    run_checked(runner, [sshd, "-t"], err=err)


def enable_and_restart_ssh(runner: Runner, *, out: TextIO, err: TextIO) -> None:
    run_checked(runner, ["systemctl", "enable", "--now", "ssh"], err=err)
    run_checked(runner, ["systemctl", "restart", "ssh"], err=err)
    log_info("ssh service is enabled and restarted.", out=out)


def configure_ufw(
    runner: Runner,
    *,
    interface: str,
    skip_ufw: bool,
    out: TextIO,
    err: TextIO,
) -> None:
    if skip_ufw:
        log_info("Skipping UFW configuration by request.", out=out)
        return

    ufw = shutil.which("ufw")
    if not ufw:
        log_warn("UFW is not installed; leaving firewall rules unchanged.", err=err)
        return

    status = runner.run([ufw, "status"], capture_output=True)
    if status.returncode != 0:
        raise RuntimeError(
            "Failed to query UFW status.\n"
            f"stdout:\n{status.stdout or ''}\n"
            f"stderr:\n{status.stderr or ''}"
        )

    if not (status.stdout or "").lower().startswith("status: active"):
        log_info("UFW is inactive; no firewall rule changes were needed.", out=out)
        return

    run_checked(
        runner,
        [ufw, "allow", "in", "on", interface, "to", "any", "port", "22", "proto", "tcp"],
        err=err,
    )
    log_info(f"Ensured UFW allows TCP/22 on {interface}.", out=out)


def setup_wsl_ssh(
    cfg: SetupConfig,
    *,
    runner: Runner,
    out: TextIO,
    err: TextIO,
) -> int:
    require_root()

    home_dir = Path("/home") / cfg.user
    if not home_dir.is_dir():
        log_warn(f"Home directory not found for {cfg.user}: {home_dir}", err=err)

    tailscale_ip = ensure_tailscale_running(runner, out=out, err=err)
    ensure_openssh_server_installed(runner, out=out, err=err)
    write_if_changed(
        cfg.ssh_dropin_path,
        render_sshd_dropin(cfg.user, allow_root_login=cfg.allow_root_login),
        out=out,
    )
    validate_sshd_config(runner, err=err)
    enable_and_restart_ssh(runner, out=out, err=err)
    configure_ufw(
        runner,
        interface=cfg.tailscale_interface,
        skip_ufw=cfg.skip_ufw,
        out=out,
        err=err,
    )

    if tailscale_ip is not None:
        log_info(f"Dokploy can target {cfg.user}@{tailscale_ip}:22", out=out)
        if cfg.allow_root_login:
            log_info(f"Dokploy can also target root@{tailscale_ip}:22 with a key.", out=out)
    log_info(
        f"Add Dokploy's public key to /home/{cfg.user}/.ssh/authorized_keys before testing access.",
        out=out,
    )
    if cfg.allow_root_login:
        log_info(
            "Add Dokploy's public key to /root/.ssh/authorized_keys for root SSH access.",
            out=out,
        )
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
        args = build_parser().parse_args(list(argv))
        cfg = compute_config(args, env=env)
        return setup_wsl_ssh(cfg, runner=runner, out=_out, err=_err)
    except SystemExit:
        raise
    except Exception as exc:
        log_error(str(exc), err=_err)
        return 1

from __future__ import annotations

import io
import subprocess
import tempfile
import unittest
from collections.abc import Sequence
from pathlib import Path

from scripts_py.cli import setup_wsl_ssh


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.responses: dict[tuple[str, ...], subprocess.CompletedProcess[str]] = {}

    def set_response(
        self,
        argv: Sequence[str],
        *,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        self.responses[tuple(argv)] = subprocess.CompletedProcess(
            args=list(argv),
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )

    def run(
        self,
        argv: Sequence[str],
        *,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        return self.responses.get(
            tuple(argv),
            subprocess.CompletedProcess(args=list(argv), returncode=0, stdout="", stderr=""),
        )


class TestSetupWslSsh(unittest.TestCase):
    def test_default_user_prefers_sudo_user(self) -> None:
        self.assertEqual(
            setup_wsl_ssh.default_user(env={"SUDO_USER": "tapiiri", "USER": "root"}),
            "tapiiri",
        )

    def test_compute_config_requires_user(self) -> None:
        args = setup_wsl_ssh.build_parser().parse_args([])
        with self.assertRaises(ValueError):
            setup_wsl_ssh.compute_config(args, env={})

    def test_render_sshd_dropin_locks_to_user(self) -> None:
        rendered = setup_wsl_ssh.render_sshd_dropin("tapiiri", allow_root_login=False)
        self.assertIn("AllowUsers tapiiri\n", rendered)
        self.assertIn("PasswordAuthentication no\n", rendered)
        self.assertIn("PermitRootLogin no\n", rendered)

    def test_render_sshd_dropin_can_allow_root_key_login(self) -> None:
        rendered = setup_wsl_ssh.render_sshd_dropin("tapiiri", allow_root_login=True)
        self.assertIn("AllowUsers tapiiri root\n", rendered)
        self.assertIn("PermitRootLogin prohibit-password\n", rendered)

    def test_write_if_changed_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "sshd.conf"
            out = io.StringIO()

            first = setup_wsl_ssh.write_if_changed(target, "content\n", out=out)
            second = setup_wsl_ssh.write_if_changed(target, "content\n", out=out)

            self.assertTrue(first)
            self.assertFalse(second)
            self.assertEqual(target.read_text(encoding="utf-8"), "content\n")

    def test_configure_ufw_noops_when_inactive(self) -> None:
        runner = FakeRunner()
        out = io.StringIO()
        err = io.StringIO()

        def fake_which(name: str) -> str | None:
            if name == "ufw":
                return "/usr/sbin/ufw"
            return None

        original_which = setup_wsl_ssh.shutil.which
        try:
            setup_wsl_ssh.shutil.which = fake_which  # type: ignore[assignment]
            runner.set_response(["/usr/sbin/ufw", "status"], stdout="Status: inactive\n")
            setup_wsl_ssh.configure_ufw(
                runner,
                interface="tailscale0",
                skip_ufw=False,
                out=out,
                err=err,
            )
        finally:
            setup_wsl_ssh.shutil.which = original_which  # type: ignore[assignment]

        self.assertEqual(
            runner.calls,
            [["/usr/sbin/ufw", "status"]],
        )

    def test_setup_wsl_ssh_runs_expected_commands(self) -> None:
        runner = FakeRunner()
        out = io.StringIO()
        err = io.StringIO()

        cfg = setup_wsl_ssh.SetupConfig(
            user="tapiiri",
            tailscale_interface="tailscale0",
            ssh_dropin_path=Path("/tmp/10-tapiiri-wsl.conf"),
            skip_ufw=True,
            allow_root_login=True,
        )

        runner.set_response(["/usr/bin/tailscale", "status", "--json"], stdout="{}")
        runner.set_response(["/usr/bin/tailscale", "ip", "-4"], stdout="100.64.0.10\n")
        runner.set_response(["dpkg", "-s", "openssh-server"], returncode=0)
        runner.set_response(["/usr/sbin/sshd", "-t"], returncode=0)
        runner.set_response(["systemctl", "enable", "--now", "ssh"], returncode=0)
        runner.set_response(["systemctl", "restart", "ssh"], returncode=0)

        original_which = setup_wsl_ssh.shutil.which
        original_geteuid = setup_wsl_ssh.os.geteuid
        try:
            setup_wsl_ssh.shutil.which = lambda name: {  # type: ignore[assignment]
                "tailscale": "/usr/bin/tailscale",
                "sshd": "/usr/sbin/sshd",
            }.get(name if isinstance(name, str) else "")
            setup_wsl_ssh.os.geteuid = lambda: 0  # type: ignore[assignment]

            rc = setup_wsl_ssh.setup_wsl_ssh(cfg, runner=runner, out=out, err=err)
        finally:
            setup_wsl_ssh.shutil.which = original_which  # type: ignore[assignment]
            setup_wsl_ssh.os.geteuid = original_geteuid  # type: ignore[assignment]
            cfg.ssh_dropin_path.unlink(missing_ok=True)

        self.assertEqual(rc, 0)
        self.assertEqual(
            runner.calls,
            [
                ["/usr/bin/tailscale", "status", "--json"],
                ["/usr/bin/tailscale", "ip", "-4"],
                ["dpkg", "-s", "openssh-server"],
                ["/usr/sbin/sshd", "-t"],
                ["systemctl", "enable", "--now", "ssh"],
                ["systemctl", "restart", "ssh"],
            ],
        )
        self.assertIn("Dokploy can target tapiiri@100.64.0.10:22", out.getvalue())
        self.assertIn("Dokploy can also target root@100.64.0.10:22 with a key.", out.getvalue())


if __name__ == "__main__":
    unittest.main()

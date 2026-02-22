from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    hint: str | None = None


class PasswordManagerBackend(Protocol):
    provider_id: str
    cli_binary: str

    def check_logged_in(self) -> CheckResult:
        raise NotImplementedError

    def format_help_message(self, *, hint: str | None) -> str:
        raise NotImplementedError

    def store_secret(self, *, entry_path: str, value: str, username: str | None) -> None:
        raise NotImplementedError


class LastPassBackend:
    provider_id = "lastpass"
    cli_binary = "lpass"

    def _run_status(self, *, lpass_path: str) -> CheckResult:
        try:
            cp = subprocess.run([lpass_path, "status"], capture_output=True, text=True)
        except OSError as e:
            return CheckResult(ok=False, hint=str(e))

        if cp.returncode == 0:
            return CheckResult(ok=True)

        hint = (cp.stderr or "").strip() or (cp.stdout or "").strip() or None
        return CheckResult(ok=False, hint=hint)

    def check_logged_in(self) -> CheckResult:
        lpass_path = shutil.which(self.cli_binary)
        if not lpass_path:
            return CheckResult(
                ok=False,
                hint=(
                    "lpass executable not found on PATH. secretspec is enabled in this repo and "
                    "will try to use a password manager CLI to provide secrets. "
                    "Install lastpass-cli (lpass) and log in."
                ),
            )

        return self._run_status(lpass_path=lpass_path)

    def format_help_message(self, *, hint: str | None) -> str:
        details = f"\n\nDetails: {hint}" if hint else ""
        return (
            "Password manager CLI is not authenticated (LastPass: lpass is not logged in).\n"
            "This repo enables devenv+secretspec, which uses a password manager CLI to "
            "provide required secrets.\n\n"
            "Fix: run `lpass login <email>` (and complete 2FA if prompted).\n"
            "Then retry (for direnv: `direnv reload`; for pre-commit: re-run the git command)."
            f"{details}"
        )

    def store_secret(self, *, entry_path: str, value: str, username: str | None) -> None:
        lpass_path = shutil.which(self.cli_binary)
        if not lpass_path:
            raise RuntimeError(
                "lpass executable not found on PATH; please install LastPass CLI (lpass)"
            )

        # Fail fast with a helpful hint if not logged in.
        res = self._run_status(lpass_path=lpass_path)
        if not res.ok:
            hint = res.hint or ""
            raise RuntimeError(
                "lpass indicates you are not logged in or cannot access the account. "
                f"Run `lpass login user@example.com` first. Details: {hint}"
            )

        cmd = [
            lpass_path,
            "add",
            "--sync=now",
            "--non-interactive",
        ]
        if username:
            cmd += ["--username", username]

        # NOTE: For the LastPass CLI shipped in Nixpkgs, `--password` is a flag and
        # the actual password value is read from stdin (NOT as a flag argument).
        cmd += ["--password", entry_path]

        subprocess.run(cmd, input=value, text=True, check=True)


def _provider_from_env() -> str:
    return os.environ.get("NIXOS_SETUP_PASSWORD_MANAGER", "lastpass").strip() or "lastpass"


def get_password_manager_backend(provider: str | None = None) -> PasswordManagerBackend:
    provider_id = (provider or _provider_from_env()).strip().lower()
    if provider_id in {"lastpass", "lpass"}:
        return LastPassBackend()

    raise ValueError(
        f"Unsupported password manager provider: {provider_id!r}. Supported providers: lastpass"
    )


def check_password_manager_logged_in(provider: str | None = None) -> CheckResult:
    return get_password_manager_backend(provider).check_logged_in()

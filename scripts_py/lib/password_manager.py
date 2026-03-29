from __future__ import annotations

import json
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

    def try_signin(self) -> CheckResult:
        """Attempt interactive signin. Return result of post-signin check."""
        raise NotImplementedError

    def format_help_message(self, *, hint: str | None) -> str:
        raise NotImplementedError

    def store_secret(self, *, entry_path: str, value: str, username: str | None) -> None:
        raise NotImplementedError


class OnePasswordBackend:
    provider_id = "onepassword"
    cli_binary = "op"

    def _run_whoami(self, *, op_path: str) -> CheckResult:
        try:
            cp = subprocess.run([op_path, "whoami"], capture_output=True, text=True)
        except OSError as e:
            return CheckResult(ok=False, hint=str(e))

        if cp.returncode == 0:
            return CheckResult(ok=True)

        hint = (cp.stderr or "").strip() or (cp.stdout or "").strip() or None
        return CheckResult(ok=False, hint=hint)

    def check_logged_in(self) -> CheckResult:
        op_path = shutil.which(self.cli_binary)
        if not op_path:
            return CheckResult(
                ok=False,
                hint=(
                    "op executable not found on PATH. secretspec is enabled in this repo and "
                    "will try to use a password manager CLI to provide secrets. "
                    "Install 1Password CLI (op) and sign in."
                ),
            )

        return self._run_whoami(op_path=op_path)

    def try_signin(self) -> CheckResult:
        op_path = shutil.which(self.cli_binary)
        if not op_path:
            return CheckResult(
                ok=False,
                hint="op executable not found on PATH.",
            )
        try:
            subprocess.run(
                [op_path, "signin"],
                check=True,
            )
        except (OSError, subprocess.CalledProcessError) as e:
            return CheckResult(ok=False, hint=str(e))
        return self._run_whoami(op_path=op_path)

    def format_help_message(self, *, hint: str | None) -> str:
        details = f"\n\nDetails: {hint}" if hint else ""
        return (
            "Password manager CLI is not authenticated (1Password: op is not signed in).\n"
            "This repo enables devenv+secretspec, which uses a password manager CLI to "
            "provide required secrets.\n\n"
            "Fix: run `op signin` (or `eval $(op signin)` in bash).\n"
            "Then retry (re-run the git command or restart `devenv shell`)."
            f"{details}"
        )

    def store_secret(self, *, entry_path: str, value: str, username: str | None) -> None:
        op_path = shutil.which(self.cli_binary)
        if not op_path:
            raise RuntimeError("op executable not found on PATH; please install 1Password CLI (op)")

        # Fail fast with a helpful hint if not signed in.
        res = self._run_whoami(op_path=op_path)
        if not res.ok:
            hint = res.hint or ""
            raise RuntimeError(
                "op indicates you are not signed in or cannot access the account. "
                f"Run `op signin` first. Details: {hint}"
            )

        # Build JSON template and pipe via stdin to avoid secrets in process args.
        fields: list[dict[str, str]] = [
            {"id": "password", "type": "CONCEALED", "value": value},
        ]
        if username:
            fields.append({"id": "username", "value": username})

        template = json.dumps(
            {"title": entry_path, "category": "LOGIN", "fields": fields},
        )

        subprocess.run(
            [op_path, "item", "create", "-"],
            input=template,
            text=True,
            check=True,
        )


def _provider_from_env() -> str:
    return os.environ.get("NIXOS_SETUP_PASSWORD_MANAGER", "onepassword").strip() or "onepassword"


def get_password_manager_backend(provider: str | None = None) -> PasswordManagerBackend:
    provider_id = (provider or _provider_from_env()).strip().lower()
    if provider_id in {"onepassword", "op", "1password"}:
        return OnePasswordBackend()

    raise ValueError(
        f"Unsupported password manager provider: {provider_id!r}. Supported providers: onepassword"
    )


def check_password_manager_logged_in(provider: str | None = None) -> CheckResult:
    return get_password_manager_backend(provider).check_logged_in()

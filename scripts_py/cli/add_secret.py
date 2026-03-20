#!/usr/bin/env python3
"""Add a secret to secretspec and a password manager in one step.

This module intentionally keeps side-effects (file IO, subprocess) small and
abstracted so tests can mock them.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import tomlkit

from scripts_py.lib.password_manager import get_password_manager_backend
from scripts_py.lib.utils import log_error, log_info
from scripts_py.repo.context import repo_root_from_script_path


@dataclass
class AddSecretOptions:
    secretspec_path: Path
    profile: str
    name: str
    value: str
    username: Optional[str]
    description: Optional[str]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, txt: str) -> None:
    path.write_text(txt, encoding="utf-8")


def _get_project_name(text: str) -> str:
    try:
        doc: Any = tomlkit.parse(text)
        proj: Any = doc.get("project")
        if proj:
            name: Any = proj.get("name")
            if isinstance(name, str):
                return name
    except Exception:
        # fall back to regex if parsing fails
        m = re.search(r"^\[project\][\s\S]*?^name\s*=\s*\"([^\"]+)\"", text, re.M)
        if m:
            return m.group(1)

    # fallback to repo directory name
    return Path.cwd().name


def _format_entry(name: str, description: Optional[str], required: bool) -> dict[str, object]:
    data: dict[str, object] = {}
    if description is not None:
        data["description"] = description
    data["required"] = required
    return data


def add_secret_to_secretspec(opts: AddSecretOptions) -> None:
    """Insert a secret definition into the secretspec TOML file using tomlkit.

    This preserves comments and formatting where possible.
    """

    txt = _read_text(opts.secretspec_path)
    # parse existing document (tomlkit preserves comments)
    doc: Any
    try:
        doc = tomlkit.parse(txt)
    except Exception:
        # start with an empty TOML document if parsing fails
        doc = tomlkit.document()

    profiles: Any = doc.get("profiles")
    if profiles is None:
        profiles = tomlkit.table()
        doc["profiles"] = profiles

    profile_tbl: Any = profiles.get(opts.profile)
    if profile_tbl is None:
        profile_tbl = tomlkit.table()
        profiles[opts.profile] = profile_tbl

    if opts.name in profile_tbl:
        raise ValueError(f"Secret {opts.name} already defined in profile {opts.profile}")

    entry_data = _format_entry(opts.name, opts.description, required=True)
    inline: Any = tomlkit.inline_table()
    for k, v in entry_data.items():
        inline[k] = v

    # assign inline table to keep one-line inline representation
    profile_tbl[opts.name] = inline

    new_txt = str(tomlkit.dumps(doc))  # type: ignore[reportUnknownMemberType]
    _write_text(opts.secretspec_path, new_txt)


def add_secret_to_password_manager(opts: AddSecretOptions, *, provider: str | None = None) -> None:
    """Store the secret value in a password manager.

    Path format: secretspec/{project}/{profile}/{key}
    """
    txt = _read_text(opts.secretspec_path)
    project = _get_project_name(txt)
    entry_path = f"secretspec/{project}/{opts.profile}/{opts.name}"

    backend = get_password_manager_backend(provider)
    backend.store_secret(entry_path=entry_path, value=opts.value, username=opts.username)


def add_secret_to_lastpass(opts: AddSecretOptions) -> None:
    """Compatibility wrapper for older callers/tests."""

    add_secret_to_password_manager(opts, provider="lastpass")


def parse_args(argv: list[str]) -> tuple[AddSecretOptions, str | None]:
    p = argparse.ArgumentParser(
        description="Add secret to secretspec and a password manager (default: LastPass)"
    )
    p.add_argument("name", help="Secret name (key)")
    p.add_argument("value", help="Secret value")
    p.add_argument("--username", help="Optional username to store alongside the secret")
    p.add_argument("--profile", default="default", help="secretspec profile to update")
    p.add_argument("--secretspec", default="secretspec.toml", help="Path to secretspec.toml")
    p.add_argument("--description", help="Optional description for the secret in secretspec")
    p.add_argument(
        "--provider",
        default=None,
        help="Password manager provider id (default: $NIXOS_SETUP_PASSWORD_MANAGER or 'lastpass')",
    )

    ns = p.parse_args(argv)
    opts = AddSecretOptions(
        secretspec_path=Path(ns.secretspec),
        profile=ns.profile,
        name=ns.name,
        value=ns.value,
        username=ns.username,
        description=ns.description,
    )
    return opts, ns.provider


def main(argv: Optional[list[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    try:
        # validate repo access (for wrapper scripts)
        repo_root_from_script_path(Path(__file__))
    except FileNotFoundError as e:
        log_error(str(e), err=sys.stderr)
        return 1

    try:
        opts, provider = parse_args(argv)
        log_info(f"Updating {opts.secretspec_path} (profile={opts.profile})...", out=sys.stdout)
        add_secret_to_secretspec(opts)
        log_info("Wrote secret definition to secretspec", out=sys.stdout)
        log_info("Storing secret value in password manager...", out=sys.stdout)
        add_secret_to_password_manager(opts, provider=provider)
        log_info("✓ Secret added to password manager and secretspec", out=sys.stdout)
        return 0
    except subprocess.CalledProcessError as e:
        log_error(f"password manager CLI failed: {e}", err=sys.stderr)
        return 2
    except Exception as e:  # pragma: no cover - defensive
        log_error(str(e), err=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

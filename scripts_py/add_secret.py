#!/usr/bin/env python3
"""Add a secret to secretspec and LastPass in one step.

This module intentionally keeps side-effects (file IO, subprocess) small and
abstracted so tests can mock them.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import tomlkit

from scripts_py.utils import log_error, log_info, repo_root_from_script_path


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
        doc = tomlkit.parse(text)
        proj = doc.get("project")
        if proj and isinstance(proj, dict):
            name = proj.get("name")
            if isinstance(name, str):
                return name
    except Exception:
        # fall back to regex if parsing fails
        m = re.search(r"^\[project\][\s\S]*?^name\s*=\s*\"([^\"]+)\"", text, re.M)
        if m:
            return m.group(1)

    # fallback to repo directory name
    return Path.cwd().name


def _ensure_profile_section(text: str, profile: str) -> str:
    """No-op when using tomlkit; left for compatibility with tests that
    construct file contents. We leave the textual append to the toml writer
    below when necessary.
    """
    return text


def _format_entry(name: str, description: Optional[str], required: bool) -> dict:
    data: dict = {}
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
    try:
        doc = tomlkit.parse(txt)
    except Exception:
        # start with an empty TOML document if parsing fails
        doc = tomlkit.document()

    profiles = doc.get("profiles")
    if profiles is None:
        profiles = tomlkit.table()
        doc["profiles"] = profiles

    profile_tbl = profiles.get(opts.profile)
    if profile_tbl is None:
        profile_tbl = tomlkit.table()
        profiles[opts.profile] = profile_tbl

    if opts.name in profile_tbl:
        raise ValueError(f"Secret {opts.name} already defined in profile {opts.profile}")

    entry_data = _format_entry(opts.name, opts.description, required=True)
    inline = tomlkit.inline_table()
    for k, v in entry_data.items():
        inline[k] = v

    # assign inline table to keep one-line inline representation
    profile_tbl[opts.name] = inline

    new_txt = tomlkit.dumps(doc)
    _write_text(opts.secretspec_path, new_txt)


def add_secret_to_lastpass(opts: AddSecretOptions) -> None:
    """Call `lpass add` to store the secret value.

    Path format: {profile}/{project}/{name}
    """
    txt = _read_text(opts.secretspec_path)
    project = _get_project_name(txt)
    path = f"{opts.profile}/{project}/{opts.name}"

    # Quick sanity checks: ensure lpass is available and the user is logged in.
    lpass_path = shutil.which("lpass")
    if not lpass_path:
        raise RuntimeError(
            "lpass executable not found on PATH; please install LastPass CLI (lpass)"
        )

    # `lpass status` returns non-zero when not logged in; capture output to show helpful hint
    try:
        status = subprocess.run([lpass_path, "status"], capture_output=True, text=True)
    except OSError as e:
        raise RuntimeError(f"Failed to execute lpass: {e}") from e

    if status.returncode != 0:
        hint = status.stderr.strip() or status.stdout.strip()
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
    if opts.username:
        cmd += ["--username", opts.username]

    # NOTE: For the LastPass CLI shipped in Nixpkgs, `--password` is a flag and
    # the actual password value is read from stdin (NOT as a flag argument).
    cmd += ["--password", path]

    # run and raise on failure
    subprocess.run(cmd, input=opts.value, text=True, check=True)


def parse_args(argv: list[str]) -> AddSecretOptions:
    p = argparse.ArgumentParser(description="Add secret to secretspec and LastPass")
    p.add_argument("name", help="Secret name (key)")
    p.add_argument("value", help="Secret value")
    p.add_argument("--username", help="Optional username to store alongside the secret")
    p.add_argument("--profile", default="default", help="secretspec profile to update")
    p.add_argument("--secretspec", default="secretspec.toml", help="Path to secretspec.toml")
    p.add_argument("--description", help="Optional description for the secret in secretspec")

    ns = p.parse_args(argv)
    return AddSecretOptions(
        secretspec_path=Path(ns.secretspec),
        profile=ns.profile,
        name=ns.name,
        value=ns.value,
        username=ns.username,
        description=ns.description,
    )


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
        opts = parse_args(argv)
        log_info(f"Updating {opts.secretspec_path} (profile={opts.profile})...", out=sys.stdout)
        add_secret_to_secretspec(opts)
        log_info("Wrote secret definition to secretspec", out=sys.stdout)
        log_info("Storing secret value in LastPass...", out=sys.stdout)
        add_secret_to_lastpass(opts)
        log_info("✓ Secret added to LastPass and secretspec", out=sys.stdout)
        return 0
    except subprocess.CalledProcessError as e:
        log_error(f"lpass failed: {e}", err=sys.stderr)
        return 2
    except Exception as e:  # pragma: no cover - defensive
        log_error(str(e), err=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

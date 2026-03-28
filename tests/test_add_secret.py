from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts_py.cli.add_secret import (
    AddSecretOptions,
    add_secret_to_password_manager,
    add_secret_to_secretspec,
)

BASE_SECRETSPEC = """[project]
name = "myproj"
revision = "1.0"

[profiles.default]
# existing comment

[profiles.development]
"""


def test_add_secret_to_secretspec(tmp_path: Path) -> None:
    p = tmp_path / "secretspec.toml"
    p.write_text(BASE_SECRETSPEC)

    opts = AddSecretOptions(
        secretspec_path=p,
        profile="default",
        name="NEW_TOKEN",
        value="secret",
        username=None,
        description="A token",
    )

    add_secret_to_secretspec(opts)

    txt = p.read_text()
    assert "NEW_TOKEN" in txt
    assert 'description = "A token"' in txt
    assert "required = true" in txt


def test_duplicate_definition_raises(tmp_path: Path) -> None:
    # place a duplicate definition inside the default profile section
    txt = (
        '[project]\nname = "myproj"\nrevision = "1.0"\n\n'
        '[profiles.default]\nNEW_TOKEN = { description = "x", required = true }\n\n'
        "[profiles.development]\n"
    )
    p = tmp_path / "secretspec.toml"
    p.write_text(txt)

    opts = AddSecretOptions(
        secretspec_path=p,
        profile="default",
        name="NEW_TOKEN",
        value="secret",
        username=None,
        description=None,
    )

    with pytest.raises(ValueError):
        add_secret_to_secretspec(opts)


def test_add_secret_to_password_manager_invokes_op(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = tmp_path / "secretspec.toml"
    p.write_text(BASE_SECRETSPEC)

    opts = AddSecretOptions(
        secretspec_path=p,
        profile="development",
        name="API_KEY",
        value="abcd",
        username="svc-user",
        description=None,
    )

    calls: list[tuple[Any, dict[str, Any]]] = []

    def fake_run(cmd: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    def _fake_which(_name: str) -> str:
        return "/bin/op"

    monkeypatch.setattr("shutil.which", _fake_which)

    add_secret_to_password_manager(opts)

    # first call is op whoami
    assert calls[0][0] == ["/bin/op", "whoami"]

    # second call is op item create -
    create_cmd: Any
    create_kwargs: dict[str, Any]
    create_cmd, create_kwargs = calls[1]

    assert create_cmd == ["/bin/op", "item", "create", "-"]
    # JSON template passed via stdin should contain the entry path and value
    assert "secretspec/myproj/development/API_KEY" in create_kwargs["input"]
    assert "abcd" in create_kwargs["input"]
    assert "svc-user" in create_kwargs["input"]
    assert create_kwargs["text"] is True
    assert create_kwargs["check"] is True

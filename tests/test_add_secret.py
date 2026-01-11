import subprocess

import pytest

from scripts_py.add_secret import (
    AddSecretOptions,
    add_secret_to_lastpass,
    add_secret_to_secretspec,
)

BASE_SECRETSPEC = """[project]
name = "myproj"
revision = "1.0"

[profiles.default]
# existing comment

[profiles.development]
"""


def test_add_secret_to_secretspec(tmp_path):
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


def test_duplicate_definition_raises(tmp_path):
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


def test_add_secret_to_lastpass_invokes_lpass(tmp_path, monkeypatch):
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

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    add_secret_to_lastpass(opts)

    # first call is lpass status
    assert calls[0][0][1] == "status"

    # second call is lpass add
    add_cmd, add_kwargs = calls[1]

    # should build path secretspec/myproj/development/API_KEY
    assert any("secretspec/myproj/development/API_KEY" in str(c) for c in add_cmd)
    assert add_kwargs["input"] == "abcd"
    assert add_kwargs["text"] is True
    assert add_kwargs["check"] is True

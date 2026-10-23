"""Guard the interpreter that the repo's Python entrypoints resolve to.

Every script under ``scripts/`` runs through ``#!/usr/bin/env python3``, and
pyright resolves project imports with the ``python3`` it finds on PATH.  Both
therefore depend on devenv's pinned ``python313.withPackages`` env coming
first — and Python packages in ``packages`` (``pkgs.pre-commit``, say)
propagate a *bare* interpreter of their own into PATH.  When one of those won,
``python3`` lost ``tomlkit``: the scripts died with ModuleNotFoundError and
pyright reported every project import as missing.

These tests only mean something inside the devenv shell, so they skip
elsewhere.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any, cast

import tomlkit

_REPO = Path(__file__).resolve().parent.parent


def _pyproject() -> dict[str, Any]:
    path = _REPO / "pyproject.toml"
    return cast(dict[str, Any], tomlkit.loads(path.read_text(encoding="utf-8")))


def _project_dependency_modules() -> list[str]:
    """Top-level module names from pyproject's runtime dependencies."""
    deps: list[str] = _pyproject()["project"]["dependencies"]
    return [re.split(r"[\[<>=!~;\s]", dep, maxsplit=1)[0] for dep in deps]


@unittest.skipUnless(os.environ.get("DEVENV_ROOT"), "not running inside the devenv shell")
class TestPythonEnv(unittest.TestCase):
    def test_path_python3_imports_project_dependencies(self) -> None:
        python3 = shutil.which("python3")
        self.assertIsNotNone(python3, "no python3 on PATH")
        assert python3 is not None

        modules = _project_dependency_modules()
        self.assertTrue(modules, "pyproject declares no dependencies to check")

        code = "import " + ", ".join(modules)
        proc = subprocess.run(
            [python3, "-c", code],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"`python3` on PATH ({python3}) cannot import {modules}.\n"
            "  → Another package in devenv.nix `packages` is propagating its own\n"
            "    interpreter ahead of pythonEnv; move pythonEnv earlier in the list.\n"
            f"{proc.stderr}",
        )

    def test_pytest_runs_on_the_pinned_interpreter(self) -> None:
        """pytest itself must come from the same env, not a propagated copy."""
        modules = _project_dependency_modules()
        for module in modules:
            with self.subTest(module=module):
                __import__(module)

        # Keep the running interpreter and the version pyright type-checks
        # against from drifting apart.
        configured: str = _pyproject()["tool"]["pyright"]["pythonVersion"]
        self.assertEqual(
            ".".join(str(p) for p in sys.version_info[:2]),
            configured,
            "pytest is running on a different Python than [tool.pyright] pythonVersion",
        )

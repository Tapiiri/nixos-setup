"""Tests for the tooling coverage audit system."""

from __future__ import annotations

import io
import json
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts_py.lib.tooling_audit import (
    AuditResult,
    CoverageRecord,
    FileTypeSpec,
    Gap,
    ToolEntry,
    classify_files,
    compute_coverage,
    format_json,
    format_table,
    load_registry,
)
from scripts_py.lib.tooling_discovery import (
    discover_all,
    discover_from_pyproject,
    discover_from_vscode_nix,
)

# ── Registry loading ─────────────────────────────────────────────────────


class TestLoadRegistry(unittest.TestCase):
    def test_loads_basic_registry(self) -> None:
        toml_text = textwrap.dedent("""\
            [file_types.python]
            extensions = [".py"]
            shebang_patterns = ["python3"]
            linters = [{ name = "ruff", source = "devenv" }]
            formatters = []
            vscode_extensions = ["ms-python.python"]
            muted = ["formatter"]
        """)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tooling-audit.toml"
            path.write_text(toml_text, encoding="utf-8")
            specs = load_registry(path)

        self.assertEqual(len(specs), 1)
        spec = specs[0]
        self.assertEqual(spec.key, "python")
        self.assertEqual(spec.extensions, (".py",))
        self.assertEqual(spec.shebang_patterns, ("python3",))
        self.assertEqual(len(spec.linters), 1)
        self.assertEqual(spec.linters[0].name, "ruff")
        self.assertEqual(spec.linters[0].category, "linter")
        self.assertEqual(spec.formatters, ())
        self.assertEqual(spec.vscode_extensions, ("ms-python.python",))
        self.assertEqual(spec.muted, ("formatter",))

    def test_loads_multiple_file_types(self) -> None:
        toml_text = textwrap.dedent("""\
            [file_types.nix]
            extensions = [".nix"]
            linters = [{ name = "nix flake check", source = "devenv" }]
            formatters = [{ name = "alejandra", source = "devenv" }]
            vscode_extensions = ["jnoortheen.nix-ide"]

            [file_types.markdown]
            extensions = [".md"]
            linters = []
            formatters = []
            vscode_extensions = []
        """)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tooling-audit.toml"
            path.write_text(toml_text, encoding="utf-8")
            specs = load_registry(path)

        self.assertEqual(len(specs), 2)
        self.assertEqual(specs[0].key, "nix")
        self.assertEqual(specs[1].key, "markdown")

    def test_empty_registry(self) -> None:
        toml_text = "[file_types]\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tooling-audit.toml"
            path.write_text(toml_text, encoding="utf-8")
            specs = load_registry(path)

        self.assertEqual(specs, [])


# ── File classification ──────────────────────────────────────────────────


class TestClassifyFiles(unittest.TestCase):
    def setUp(self) -> None:
        self.specs = [
            FileTypeSpec(
                key="python",
                extensions=(".py",),
                glob_patterns=(),
                shebang_patterns=("python3",),
                linters=(),
                formatters=(),
                vscode_extensions=(),
                muted=(),
            ),
            FileTypeSpec(
                key="nix",
                extensions=(".nix",),
                glob_patterns=(),
                shebang_patterns=(),
                linters=(),
                formatters=(),
                vscode_extensions=(),
                muted=(),
            ),
            FileTypeSpec(
                key="github-actions",
                extensions=(),
                glob_patterns=(".github/workflows/*.yml",),
                shebang_patterns=(),
                linters=(),
                formatters=(),
                vscode_extensions=(),
                muted=(),
            ),
            FileTypeSpec(
                key="yaml",
                extensions=(".yml", ".yaml"),
                glob_patterns=(),
                shebang_patterns=(),
                linters=(),
                formatters=(),
                vscode_extensions=(),
                muted=(),
            ),
        ]

    def test_classifies_by_extension(self) -> None:
        files = ["foo.py", "bar.nix", "baz.txt"]
        classified, unmapped = classify_files(files, self.specs)

        self.assertEqual(classified["python"], ["foo.py"])
        self.assertEqual(classified["nix"], ["bar.nix"])
        self.assertIn("baz.txt", unmapped)

    def test_classifies_by_glob(self) -> None:
        files = [".github/workflows/ci.yml", "config.yml"]
        classified, unmapped = classify_files(files, self.specs)

        # ci.yml matches both github-actions (glob) AND yaml (extension)
        self.assertIn(".github/workflows/ci.yml", classified["github-actions"])
        self.assertIn(".github/workflows/ci.yml", classified["yaml"])
        # config.yml matches yaml only
        self.assertIn("config.yml", classified["yaml"])

    def test_classifies_by_shebang(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Extensionless file with python shebang
            script = Path(tmp) / "myscript"
            script.write_text("#!/usr/bin/env -S python3\nprint('hi')\n")

            files = ["myscript"]
            classified, unmapped = classify_files(files, self.specs, repo_root=Path(tmp))

            self.assertIn("myscript", classified["python"])
            self.assertEqual(unmapped, [])

    def test_unmapped_files(self) -> None:
        files = ["README.txt", "data.csv"]
        classified, unmapped = classify_files(files, self.specs)

        self.assertEqual(sorted(unmapped), ["README.txt", "data.csv"])


# ── Coverage computation ─────────────────────────────────────────────────


class TestComputeCoverage(unittest.TestCase):
    def test_full_coverage_no_gaps(self) -> None:
        specs = [
            FileTypeSpec(
                key="python",
                extensions=(".py",),
                glob_patterns=(),
                shebang_patterns=(),
                linters=(ToolEntry("ruff", "devenv", "linter"),),
                formatters=(ToolEntry("ruff fix", "vscode", "formatter"),),
                vscode_extensions=("ms-python.python",),
                muted=(),
            ),
        ]
        classified = {"python": ["foo.py", "bar.py"]}

        result = compute_coverage(specs, classified, [])
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0].gaps, [])

    def test_missing_linter_produces_gap(self) -> None:
        specs = [
            FileTypeSpec(
                key="json",
                extensions=(".json",),
                glob_patterns=(),
                shebang_patterns=(),
                linters=(),
                formatters=(),
                vscode_extensions=(),
                muted=(),
            ),
        ]
        classified = {"json": ["data.json"]}

        result = compute_coverage(specs, classified, [])
        gaps = result.records[0].gaps
        self.assertEqual(len(gaps), 3)  # linter + formatter + vscode_extension
        cats = {g.category for g in gaps}
        self.assertEqual(cats, {"linter", "formatter", "vscode_extension"})
        self.assertFalse(any(g.muted for g in gaps))

    def test_muted_gap_is_flagged(self) -> None:
        specs = [
            FileTypeSpec(
                key="json",
                extensions=(".json",),
                glob_patterns=(),
                shebang_patterns=(),
                linters=(),
                formatters=(),
                vscode_extensions=(),
                muted=("linter", "formatter", "vscode_extension"),
            ),
        ]
        classified = {"json": ["data.json"]}

        result = compute_coverage(specs, classified, [])
        gaps = result.records[0].gaps
        self.assertTrue(all(g.muted for g in gaps))

    def test_no_gaps_for_empty_file_type(self) -> None:
        """If no files matched a type, there should be no gaps."""
        specs = [
            FileTypeSpec(
                key="python",
                extensions=(".py",),
                glob_patterns=(),
                shebang_patterns=(),
                linters=(),
                formatters=(),
                vscode_extensions=(),
                muted=(),
            ),
        ]
        classified = {"python": []}

        result = compute_coverage(specs, classified, [])
        self.assertEqual(result.records[0].gaps, [])

    def test_discovered_tools_are_merged(self) -> None:
        specs = [
            FileTypeSpec(
                key="python",
                extensions=(".py",),
                glob_patterns=(),
                shebang_patterns=(),
                linters=(),
                formatters=(),
                vscode_extensions=(),
                muted=(),
            ),
        ]
        classified = {"python": ["foo.py"]}
        discovered = [
            ToolEntry("ruff", "pyproject:python", "linter"),
            ToolEntry("ms-python.python", "vscode-nix:python", "vscode_extension"),
        ]

        result = compute_coverage(specs, classified, [], discovered=discovered)
        rec = result.records[0]
        self.assertEqual(len(rec.linters), 1)
        self.assertEqual(rec.linters[0].name, "ruff")
        self.assertIn("ms-python.python", rec.vscode_extensions)

    def test_discovered_tools_do_not_duplicate(self) -> None:
        specs = [
            FileTypeSpec(
                key="python",
                extensions=(".py",),
                glob_patterns=(),
                shebang_patterns=(),
                linters=(ToolEntry("ruff", "devenv", "linter"),),
                formatters=(),
                vscode_extensions=("ms-python.python",),
                muted=("formatter",),
            ),
        ]
        classified = {"python": ["foo.py"]}
        discovered = [
            ToolEntry("ruff", "pyproject:python", "linter"),
            ToolEntry("ms-python.python", "vscode-nix:python", "vscode_extension"),
        ]

        result = compute_coverage(specs, classified, [], discovered=discovered)
        rec = result.records[0]
        # Should not duplicate ruff.
        self.assertEqual(len(rec.linters), 1)
        # Should not duplicate vscode ext.
        self.assertEqual(rec.vscode_extensions.count("ms-python.python"), 1)


# ── Output formatting ────────────────────────────────────────────────────


class TestFormatTable(unittest.TestCase):
    def test_table_contains_file_type(self) -> None:
        result = AuditResult(
            records=[
                CoverageRecord(
                    file_type="python",
                    matched_files=["foo.py"],
                    linters=[ToolEntry("ruff", "devenv", "linter")],
                    formatters=[],
                    vscode_extensions=["ms-python.python"],
                    muted=["formatter"],
                    gaps=[Gap("python", "formatter", muted=True)],
                ),
            ],
        )
        table = format_table(result)
        self.assertIn("python", table)
        self.assertIn("ruff", table)
        self.assertIn("ms-python.python", table)
        self.assertIn("muted", table.lower())

    def test_table_shows_unmapped(self) -> None:
        result = AuditResult(
            records=[],
            unmapped_files=["weirdfile.xyz"],
        )
        table = format_table(result)
        self.assertIn("weirdfile.xyz", table)


class TestFormatJson(unittest.TestCase):
    def test_json_is_valid(self) -> None:
        result = AuditResult(
            records=[
                CoverageRecord(
                    file_type="nix",
                    matched_files=["flake.nix"],
                    linters=[ToolEntry("nix flake check", "devenv", "linter")],
                    formatters=[ToolEntry("alejandra", "devenv", "formatter")],
                    vscode_extensions=["jnoortheen.nix-ide"],
                    muted=[],
                    gaps=[],
                ),
            ],
            unmapped_files=["result"],
        )
        raw = format_json(result)
        data = json.loads(raw)

        self.assertEqual(len(data["records"]), 1)
        self.assertEqual(data["records"][0]["file_type"], "nix")
        self.assertEqual(data["summary"]["unmuted_gaps"], 0)
        self.assertEqual(data["unmapped_files"], ["result"])


# ── Discovery: pyproject.toml ────────────────────────────────────────────


class TestDiscoverFromPyproject(unittest.TestCase):
    def test_detects_ruff(self) -> None:
        pyproject_text = textwrap.dedent("""\
            [tool.ruff]
            line-length = 100
        """)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "pyproject.toml").write_text(pyproject_text, encoding="utf-8")
            tools = discover_from_pyproject(Path(tmp))

        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, "ruff")
        self.assertEqual(tools[0].category, "linter")
        self.assertIn("python", tools[0].source)

    def test_no_pyproject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tools = discover_from_pyproject(Path(tmp))
        self.assertEqual(tools, [])


# ── Discovery: VSCode Nix ────────────────────────────────────────────────


class TestDiscoverFromVscodeNix(unittest.TestCase):
    def test_detects_pkgs_extensions(self) -> None:
        nix_content = textwrap.dedent("""\
            {pkgs, ...}: let
              PythonExt = pkgs.vscode-extensions.ms-python.python;
              RuffExt = pkgs.vscode-extensions.charliermarsh.ruff;
            in {}
        """)
        with tempfile.TemporaryDirectory() as tmp:
            nix_dir = Path(tmp) / "home" / "features" / "vscode"
            nix_dir.mkdir(parents=True)
            (nix_dir / "default.nix").write_text(nix_content, encoding="utf-8")
            tools = discover_from_vscode_nix(Path(tmp))

        names = {t.name for t in tools}
        self.assertIn("ms-python.python", names)
        self.assertIn("charliermarsh.ruff", names)
        self.assertTrue(all(t.category == "vscode_extension" for t in tools))

    def test_detects_marketplace_extensions(self) -> None:
        nix_content = textwrap.dedent("""\
            {pkgs, ...}: let
              Ext = pkgs.vscode-utils.buildVscodeMarketplaceExtension {
                mktplcRef = {
                  publisher = "1Password";
                  name = "op-vscode";
                  version = "1.0.5";
                  hash = "sha256-xxx";
                };
              };
            in {}
        """)
        with tempfile.TemporaryDirectory() as tmp:
            nix_dir = Path(tmp) / "home" / "features" / "vscode"
            nix_dir.mkdir(parents=True)
            (nix_dir / "default.nix").write_text(nix_content, encoding="utf-8")
            tools = discover_from_vscode_nix(Path(tmp))

        # 1Password.op-vscode is in the "_" prefixed (unmapped) category,
        # so it should NOT appear in the discovered tools for file types.
        self.assertEqual(tools, [])

    def test_no_nix_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tools = discover_from_vscode_nix(Path(tmp))
        self.assertEqual(tools, [])


# ── Discovery: discover_all ──────────────────────────────────────────────


class TestDiscoverAll(unittest.TestCase):
    def test_deduplicates(self) -> None:
        def source_a(_: Path) -> list[ToolEntry]:
            return [ToolEntry("ruff", "pyproject:python", "linter")]

        def source_b(_: Path) -> list[ToolEntry]:
            return [ToolEntry("ruff", "pyproject:python", "linter")]

        with tempfile.TemporaryDirectory() as tmp:
            tools = discover_all(Path(tmp), sources=[source_a, source_b])

        self.assertEqual(len(tools), 1)


# ── CLI integration ──────────────────────────────────────────────────────


class TestAuditCli(unittest.TestCase):
    def _make_repo(self, tmp: str) -> Path:
        """Create a minimal fake repo structure for testing."""
        root = Path(tmp)
        # Registry
        toml_text = textwrap.dedent("""\
            [file_types.python]
            extensions = [".py"]
            linters = [{ name = "ruff", source = "devenv" }]
            formatters = [{ name = "ruff fix", source = "vscode" }]
            vscode_extensions = ["ms-python.python"]

            [file_types.json]
            extensions = [".json"]
            linters = []
            formatters = []
            vscode_extensions = []
            muted = ["linter", "formatter", "vscode_extension"]
        """)
        (root / "tooling-audit.toml").write_text(toml_text, encoding="utf-8")
        # Fake files
        (root / "foo.py").write_text("print('hi')\n")
        (root / "data.json").write_text("{}\n")
        return root

    def test_advisory_returns_zero(self) -> None:
        from scripts_py.cli.audit_tooling import audit

        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            out, err = io.StringIO(), io.StringIO()
            with patch(
                "scripts_py.cli.audit_tooling.git_ls_files",
                return_value=["foo.py", "data.json"],
            ):
                rc = audit(
                    repo_root=root,
                    registry_path=root / "tooling-audit.toml",
                    out=out,
                    err=err,
                    strict=False,
                    no_discover=True,
                )
            self.assertEqual(rc, 0)
            self.assertIn("python", out.getvalue())

    def test_strict_with_unmuted_gap_returns_one(self) -> None:
        from scripts_py.cli.audit_tooling import audit

        toml_text = textwrap.dedent("""\
            [file_types.json]
            extensions = [".json"]
            linters = []
            formatters = []
            vscode_extensions = []
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tooling-audit.toml").write_text(toml_text, encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with patch(
                "scripts_py.cli.audit_tooling.git_ls_files",
                return_value=["data.json"],
            ):
                rc = audit(
                    repo_root=root,
                    registry_path=root / "tooling-audit.toml",
                    out=out,
                    err=err,
                    strict=True,
                    no_discover=True,
                )
            self.assertEqual(rc, 1)

    def test_strict_with_only_muted_gaps_returns_zero(self) -> None:
        from scripts_py.cli.audit_tooling import audit

        toml_text = textwrap.dedent("""\
            [file_types.json]
            extensions = [".json"]
            linters = []
            formatters = []
            vscode_extensions = []
            muted = ["linter", "formatter", "vscode_extension"]
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tooling-audit.toml").write_text(toml_text, encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with patch(
                "scripts_py.cli.audit_tooling.git_ls_files",
                return_value=["data.json"],
            ):
                rc = audit(
                    repo_root=root,
                    registry_path=root / "tooling-audit.toml",
                    out=out,
                    err=err,
                    strict=True,
                    no_discover=True,
                )
            self.assertEqual(rc, 0)

    def test_json_output_is_valid(self) -> None:
        from scripts_py.cli.audit_tooling import audit

        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            out, err = io.StringIO(), io.StringIO()
            with patch(
                "scripts_py.cli.audit_tooling.git_ls_files",
                return_value=["foo.py", "data.json"],
            ):
                rc = audit(
                    repo_root=root,
                    registry_path=root / "tooling-audit.toml",
                    out=out,
                    err=err,
                    json_output=True,
                    no_discover=True,
                )
            self.assertEqual(rc, 0)
            data = json.loads(out.getvalue())
            self.assertIn("records", data)
            self.assertIn("summary", data)

    def test_missing_registry_returns_two(self) -> None:
        from scripts_py.cli.audit_tooling import audit

        with tempfile.TemporaryDirectory() as tmp:
            out, err = io.StringIO(), io.StringIO()
            rc = audit(
                repo_root=Path(tmp),
                registry_path=Path(tmp) / "nonexistent.toml",
                out=out,
                err=err,
            )
            self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()

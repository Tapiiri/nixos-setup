"""Tests for scripts_py.lib.depmap — AST-based import dependency graph."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts_py.lib.depmap import (
    affected_tests,
    build_import_graph,
    parse_imports,
    resolve_to_repo_path,
    transitive_deps,
)


class TestParseImports(unittest.TestCase):
    def test_simple_import(self) -> None:
        src = "import os\nimport sys\n"
        self.assertEqual(parse_imports(src), {"os", "sys"})

    def test_from_import(self) -> None:
        src = "from pathlib import Path\nfrom scripts_py.lib.utils import log_info\n"
        self.assertEqual(parse_imports(src), {"pathlib", "scripts_py.lib.utils"})

    def test_mixed(self) -> None:
        src = "import json\nfrom scripts_py.repo.context import RepoMarkers\n"
        self.assertEqual(parse_imports(src), {"json", "scripts_py.repo.context"})

    def test_syntax_error_returns_empty(self) -> None:
        self.assertEqual(parse_imports("def broken("), set())

    def test_empty_source(self) -> None:
        self.assertEqual(parse_imports(""), set())

    def test_relative_import_without_module_ignored(self) -> None:
        # ``from . import foo`` has node.module == None → skipped.
        src = "from . import foo\n"
        self.assertEqual(parse_imports(src), set())


class TestResolveToRepoPath(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        # Create a minimal package structure.
        (self.root / "scripts_py" / "cli").mkdir(parents=True)
        (self.root / "scripts_py" / "__init__.py").write_text("")
        (self.root / "scripts_py" / "cli" / "__init__.py").write_text("")
        (self.root / "scripts_py" / "cli" / "rebuild.py").write_text("# rebuild")
        (self.root / "tests").mkdir()
        (self.root / "tests" / "__init__.py").write_text("")
        (self.root / "tests" / "test_rebuild.py").write_text("# test")

    def tearDown(self) -> None:
        self.td.cleanup()

    def test_resolves_dotted_module(self) -> None:
        result = resolve_to_repo_path("scripts_py.cli.rebuild", self.root)
        self.assertIsNotNone(result)
        self.assertEqual(result, self.root / "scripts_py" / "cli" / "rebuild.py")

    def test_resolves_package_init(self) -> None:
        result = resolve_to_repo_path("scripts_py.cli", self.root)
        self.assertIsNotNone(result)
        self.assertEqual(result, self.root / "scripts_py" / "cli" / "__init__.py")

    def test_returns_none_for_stdlib(self) -> None:
        self.assertIsNone(resolve_to_repo_path("os.path", self.root))

    def test_returns_none_for_third_party(self) -> None:
        self.assertIsNone(resolve_to_repo_path("pytest", self.root))

    def test_returns_none_for_nonexistent(self) -> None:
        self.assertIsNone(resolve_to_repo_path("scripts_py.nonexistent", self.root))

    def test_resolves_tests_module(self) -> None:
        result = resolve_to_repo_path("tests.test_rebuild", self.root)
        self.assertIsNotNone(result)
        self.assertEqual(result, self.root / "tests" / "test_rebuild.py")


class TestBuildImportGraph(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)

        # Build a small two-module package + one test.
        sp = self.root / "scripts_py" / "lib"
        sp.mkdir(parents=True)
        (self.root / "scripts_py" / "__init__.py").write_text("")
        (sp / "__init__.py").write_text("")
        (sp / "utils.py").write_text("# leaf module\n")
        (sp / "foo.py").write_text("from scripts_py.lib.utils import log_info\n")

        tests = self.root / "tests"
        tests.mkdir()
        (tests / "__init__.py").write_text("")
        (tests / "test_foo.py").write_text("from scripts_py.lib.foo import something\n")

    def tearDown(self) -> None:
        self.td.cleanup()

    def test_graph_has_expected_edges(self) -> None:
        graph = build_import_graph(self.root)
        foo_py = self.root / "scripts_py" / "lib" / "foo.py"
        utils_py = self.root / "scripts_py" / "lib" / "utils.py"
        test_foo_py = self.root / "tests" / "test_foo.py"

        # foo.py imports utils.py
        self.assertIn(utils_py, graph.get(foo_py, set()))

        # test_foo.py imports foo.py
        self.assertIn(foo_py, graph.get(test_foo_py, set()))

        # utils.py has no internal deps
        self.assertEqual(graph.get(utils_py, set()), set())


class TestTransitiveDeps(unittest.TestCase):
    def test_linear_chain(self) -> None:
        a, b, c = Path("a"), Path("b"), Path("c")
        graph = {a: {b}, b: {c}, c: set()}
        self.assertEqual(transitive_deps(graph, a), {b, c})

    def test_diamond(self) -> None:
        a, b, c, d = Path("a"), Path("b"), Path("c"), Path("d")
        graph = {a: {b, c}, b: {d}, c: {d}, d: set()}
        self.assertEqual(transitive_deps(graph, a), {b, c, d})

    def test_cycle_safe(self) -> None:
        a, b = Path("a"), Path("b")
        graph = {a: {b}, b: {a}}
        self.assertEqual(transitive_deps(graph, a), {b})

    def test_no_deps(self) -> None:
        a = Path("a")
        graph: dict[Path, set[Path]] = {a: set()}
        self.assertEqual(transitive_deps(graph, a), set())

    def test_unknown_file(self) -> None:
        x = Path("x")
        graph: dict[Path, set[Path]] = {}
        self.assertEqual(transitive_deps(graph, x), set())


class TestAffectedTests(unittest.TestCase):
    def test_direct_test_change(self) -> None:
        tf = Path("/repo/tests/test_a.py")
        src = Path("/repo/scripts_py/a.py")
        graph = {tf: {src}, src: set()}
        result = affected_tests(graph, {tf})
        self.assertEqual(result, {tf})

    def test_transitive_source_change(self) -> None:
        tf = Path("/repo/tests/test_a.py")
        src = Path("/repo/scripts_py/a.py")
        lib = Path("/repo/scripts_py/lib/utils.py")
        graph = {tf: {src}, src: {lib}, lib: set()}
        result = affected_tests(graph, {lib})
        self.assertEqual(result, {tf})

    def test_unrelated_change_not_affected(self) -> None:
        tf = Path("/repo/tests/test_a.py")
        src = Path("/repo/scripts_py/a.py")
        other = Path("/repo/scripts_py/b.py")
        graph = {tf: {src}, src: set(), other: set()}
        result = affected_tests(graph, {other})
        self.assertEqual(result, set())

    def test_source_files_not_included_in_result(self) -> None:
        """Only test files are returned, not the changed source files themselves."""
        tf = Path("/repo/tests/test_a.py")
        src = Path("/repo/scripts_py/a.py")
        graph = {tf: {src}, src: set()}
        result = affected_tests(graph, {src})
        self.assertNotIn(src, result)
        self.assertEqual(result, {tf})

    def test_conftest_excluded(self) -> None:
        """conftest.py should never appear in affected tests (no test functions)."""
        conftest = Path("/repo/tests/conftest.py")
        tf = Path("/repo/tests/test_a.py")
        src = Path("/repo/scripts_py/a.py")
        graph = {conftest: {src}, tf: {src}, src: set()}
        result = affected_tests(graph, {src})
        self.assertNotIn(conftest, result)
        self.assertEqual(result, {tf})


if __name__ == "__main__":
    unittest.main()

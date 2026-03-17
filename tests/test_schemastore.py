from __future__ import annotations

import unittest

from scripts_py.lib.schemastore import (
    CatalogSchema,
    choose_schema_for_file,
    match_filematch,
    pattern_specificity,
)


class TestSchemaStoreMatching(unittest.TestCase):
    def test_match_basename_pattern_matches_anywhere(self) -> None:
        self.assertTrue(match_filematch(".github/workflows/ci.yml", "ci.yml"))
        self.assertTrue(match_filematch("foo/bar/appveyor.yml", "appveyor.yml"))
        self.assertFalse(match_filematch("foo/bar/appveyor.yaml", "appveyor.yml"))

    def test_match_path_glob(self) -> None:
        self.assertTrue(match_filematch(".github/dependabot.yml", "**/.github/dependabot.yml"))
        self.assertTrue(
            match_filematch("a/b/.github/workflows/test.yaml", "**/.github/workflows/*.yaml")
        )
        self.assertFalse(
            match_filematch("a/b/.github/workflows/test.yml", "**/.github/workflows/*.yaml")
        )

    def test_pattern_specificity_prefers_exact(self) -> None:
        exact = pattern_specificity(".github/dependabot.yml")
        glob = pattern_specificity("**/.github/dependabot.yml")
        self.assertGreater(exact, glob)

    def test_choose_schema_for_file_prefers_more_specific(self) -> None:
        schemas = [
            CatalogSchema(
                name="generic-workflow",
                url="https://example.invalid/workflow.json",
                description=None,
                file_match=("**/.github/workflows/*.yml",),
            ),
            CatalogSchema(
                name="specific-ci",
                url="https://example.invalid/ci.json",
                description=None,
                file_match=("**/.github/workflows/ci.yml",),
            ),
        ]

        chosen = choose_schema_for_file(".github/workflows/ci.yml", schemas)
        assert chosen is not None
        schema, pattern = chosen
        self.assertEqual(schema.name, "specific-ci")
        self.assertEqual(pattern, "**/.github/workflows/ci.yml")


class TestSchemaStoreIndex(unittest.TestCase):
    """Guards against false-positive schema matches in the committed index."""

    def test_index_does_not_map_files_under_schemas_dir(self) -> None:
        """The schemas/ directory contains tooling artifacts, not user configs."""
        import json
        from pathlib import Path

        repo_root = Path(__file__).resolve().parent.parent
        index_path = repo_root / "schemas" / "schemastore-index.json"
        if not index_path.exists():
            self.skipTest("schemastore-index.json not found")

        index = json.loads(index_path.read_text(encoding="utf-8"))
        bad = [f for f in index.get("files", {}) if f.startswith("schemas/")]
        self.assertEqual(
            bad,
            [],
            f"Index should not map files under schemas/ — found: {bad}",
        )


if __name__ == "__main__":
    unittest.main()

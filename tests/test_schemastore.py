from __future__ import annotations

import unittest

from scripts_py.schemastore import (
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


if __name__ == "__main__":
    unittest.main()

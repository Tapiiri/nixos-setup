from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from scripts_py.utils import RepoMarkers, bootstrap_repo_import_path, find_upwards


class TestUtils(unittest.TestCase):
    def test_find_upwards_requires_markers(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "repo"
            root.mkdir()
            (root / "flake.nix").write_text("{}", encoding="utf-8")
            (root / "scripts_py").mkdir()

            nested = root / "x" / "y"
            nested.mkdir(parents=True)

            markers = RepoMarkers(files=("flake.nix",), dirs=("scripts_py",))
            found = find_upwards(nested, markers=markers)
            self.assertEqual(found, root)

            # If markers don't match, we get None
            missing = RepoMarkers(files=("nope",), dirs=())
            self.assertIsNone(find_upwards(nested, markers=missing))

    def test_bootstrap_repo_import_path_inserts_repo_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "repo"
            root.mkdir()
            (root / "flake.nix").write_text("{}", encoding="utf-8")
            (root / "scripts_py").mkdir()

            scripts_dir = root / "scripts"
            scripts_dir.mkdir()
            script = scripts_dir / "tool"
            script.write_text("#", encoding="utf-8")

            markers = RepoMarkers(files=("flake.nix",), dirs=("scripts_py",))

            # Ensure we don't leak sys.path across tests.
            old = list(sys.path)
            try:
                sys.path = [p for p in sys.path if p != str(root)]
                repo = bootstrap_repo_import_path(script_file=script, markers=markers)
                self.assertEqual(repo, root)
                self.assertEqual(sys.path[0], str(root))
            finally:
                sys.path = old


if __name__ == "__main__":
    unittest.main()

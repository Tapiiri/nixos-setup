from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from scripts_py.import_dotfiles import ImportPaths, copy_one, planned_imports


class TestImportDotfiles(unittest.TestCase):
    def test_planned_imports(self):
        paths = ImportPaths(
            repo_root=Path("/repo"),
            dot_home=Path("/repo/dotfiles/home"),
            dot_config=Path("/repo/dotfiles/config"),
            home_dir=Path("/home/u"),
        )

        pairs = planned_imports(paths, from_home=["bashrc"], from_config=["git"])
        self.assertEqual(
            pairs,
            [
                (Path("/home/u/.bashrc"), Path("/repo/dotfiles/home/bashrc")),
                (Path("/home/u/.config/git"), Path("/repo/dotfiles/config/git")),
            ],
        )

    def test_copy_one_missing_source_warns(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            out = io.StringIO()
            err = io.StringIO()
            rc = copy_one(tmp / "missing", tmp / "dst", out=out, err=err)
            self.assertEqual(rc, 0)
            self.assertIn("[WARN]", err.getvalue())

    def test_copy_one_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            src = tmp / "src"
            src.write_text("hello", encoding="utf-8")
            dst = tmp / "dst"
            dst.write_text("existing", encoding="utf-8")

            out = io.StringIO()
            err = io.StringIO()
            rc = copy_one(src, dst, out=out, err=err)
            self.assertEqual(rc, 0)
            self.assertIn("[SKIP]", err.getvalue())
            self.assertEqual(dst.read_text(encoding="utf-8"), "existing")

    def test_copy_one_copies_file(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            src = tmp / "src"
            src.write_text("hello", encoding="utf-8")
            dst = tmp / "out" / "dst"

            out = io.StringIO()
            err = io.StringIO()
            rc = copy_one(src, dst, out=out, err=err)
            self.assertEqual(rc, 0)
            self.assertTrue(dst.exists())
            self.assertEqual(dst.read_text(encoding="utf-8"), "hello")
            self.assertIn("[OK]", out.getvalue())

    def test_copy_one_copies_directory(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            src = tmp / "srcdir"
            (src / "sub").mkdir(parents=True)
            (src / "sub" / "a.txt").write_text("a", encoding="utf-8")
            dst = tmp / "dstdir"

            out = io.StringIO()
            err = io.StringIO()
            rc = copy_one(src, dst, out=out, err=err)
            self.assertEqual(rc, 0)
            self.assertTrue((dst / "sub" / "a.txt").is_file())


if __name__ == "__main__":
    unittest.main()

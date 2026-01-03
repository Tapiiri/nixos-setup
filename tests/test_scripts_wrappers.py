from __future__ import annotations

import runpy
import unittest
from pathlib import Path
from unittest.mock import patch


class TestScriptsWrappers(unittest.TestCase):
    def test_scripts_wrapper_bootstrap_imports_scripts_py(self) -> None:
        """Wrapper scripts should be runnable without ModuleNotFoundError.

        This mainly guards the common pattern: wrapper in scripts/ that imports
        scripts_py/ via sys.path bootstrapping.
        """

        wrapper = Path(__file__).resolve().parent.parent / "scripts" / "sync-github-labels"

        # pytest injects argv like "-q" and "tests"; isolate it so argparse doesn't fail.
        with patch("sys.argv", [str(wrapper), "--dry-run"]):
            try:
                runpy.run_path(str(wrapper), run_name="__main__")
            except ModuleNotFoundError as e:
                self.fail(f"Wrapper failed to import due to missing module: {e}")
            except SystemExit:
                # The script exits via SystemExit (normal for CLI entrypoints).
                pass


if __name__ == "__main__":
    unittest.main()

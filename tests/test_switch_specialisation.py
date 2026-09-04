from __future__ import annotations

import tempfile
import unittest
from collections.abc import Sequence
from pathlib import Path

from scripts_py.cli.switch_specialisation import (
    build_switch_argv,
    list_specialisations,
    main,
    switch_specialisation,
)

FAKE_SPEC_DIR = "/run/current-system/specialisation"
FAKE_BASE_BIN = "/run/current-system/bin/switch-to-configuration"


class CapturingRunner:
    """Test double that records calls and returns pre-configured exit codes."""

    def __init__(self, return_codes: list[int] | None = None) -> None:
        self._codes = iter(return_codes or [])
        self.calls: list[list[str]] = []

    def run(self, argv: Sequence[str]) -> int:
        self.calls.append(list(argv))
        return next(self._codes)


class TestBuildSwitchArgv(unittest.TestCase):
    def test_named_specialisation_uses_specialisation_path(self) -> None:
        argv = build_switch_argv("alpha")
        self.assertIn(f"{FAKE_SPEC_DIR}/alpha/bin/switch-to-configuration", argv)

    def test_named_specialisation_starts_with_sudo(self) -> None:
        argv = build_switch_argv("alpha")
        self.assertEqual(argv[0], "sudo")

    def test_named_specialisation_ends_with_switch(self) -> None:
        argv = build_switch_argv("alpha")
        self.assertEqual(argv[-1], "switch")

    def test_none_uses_base_binary(self) -> None:
        argv = build_switch_argv(None)
        self.assertIn(FAKE_BASE_BIN, argv)

    def test_base_string_uses_base_binary(self) -> None:
        argv = build_switch_argv("base")
        self.assertIn(FAKE_BASE_BIN, argv)

    def test_base_does_not_contain_specialisation_path(self) -> None:
        argv = build_switch_argv(None)
        self.assertNotIn("specialisation", " ".join(argv[1:-1]))

    def test_custom_dirs_are_respected(self) -> None:
        argv = build_switch_argv(
            "myspec",
            specialisation_dir="/custom/spec",
            base_switch_bin="/custom/base/switch",
        )
        self.assertIn("/custom/spec/myspec/bin/switch-to-configuration", argv)

    def test_custom_base_bin_respected_for_none(self) -> None:
        argv = build_switch_argv(
            None,
            specialisation_dir="/custom/spec",
            base_switch_bin="/custom/base/switch",
        )
        self.assertIn("/custom/base/switch", argv)


class TestListSpecialisations(unittest.TestCase):
    def test_returns_sorted_directory_names(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            for name in ("alpha", "charlie", "bravo"):
                (Path(d) / name).mkdir()
            result = list_specialisations(d)
        self.assertEqual(result, ["alpha", "bravo", "charlie"])

    def test_empty_directory_returns_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            result = list_specialisations(d)
        self.assertEqual(result, [])

    def test_nonexistent_directory_returns_empty_list(self) -> None:
        result = list_specialisations("/does/not/exist")
        self.assertEqual(result, [])

    def test_ignores_files(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "alpha").mkdir()
            (Path(d) / "readme.txt").write_text("hi")
            result = list_specialisations(d)
        self.assertEqual(result, ["alpha"])


class TestSwitchSpecialisation(unittest.TestCase):
    def test_runs_correct_argv_for_named(self) -> None:
        runner = CapturingRunner(return_codes=[0])
        switch_specialisation("alpha", runner)
        self.assertIn(f"{FAKE_SPEC_DIR}/alpha/bin/switch-to-configuration", runner.calls[0])

    def test_runs_correct_argv_for_base(self) -> None:
        runner = CapturingRunner(return_codes=[0])
        switch_specialisation(None, runner)
        self.assertIn(FAKE_BASE_BIN, runner.calls[0])

    def test_returns_runner_exit_code(self) -> None:
        runner = CapturingRunner(return_codes=[42])
        rc = switch_specialisation("alpha", runner)
        self.assertEqual(rc, 42)

    def test_only_one_subprocess_call(self) -> None:
        runner = CapturingRunner(return_codes=[0])
        switch_specialisation("alpha", runner)
        self.assertEqual(len(runner.calls), 1)


class TestMain(unittest.TestCase):
    def test_switches_named_specialisation(self) -> None:
        runner = CapturingRunner(return_codes=[0])
        rc = main(["alpha"], runner=runner)
        self.assertEqual(rc, 0)
        self.assertIn("alpha", " ".join(runner.calls[0]))

    def test_no_args_switches_to_base(self) -> None:
        runner = CapturingRunner(return_codes=[0])
        rc = main([], runner=runner)
        self.assertEqual(rc, 0)
        self.assertIn(FAKE_BASE_BIN, runner.calls[0])

    def test_base_arg_switches_to_base(self) -> None:
        runner = CapturingRunner(return_codes=[0])
        main(["base"], runner=runner)
        self.assertIn(FAKE_BASE_BIN, runner.calls[0])

    def test_returns_nonzero_exit_code(self) -> None:
        runner = CapturingRunner(return_codes=[1])
        rc = main(["alpha"], runner=runner)
        self.assertEqual(rc, 1)

    def test_list_flag_prints_specialisations(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            for name in ("alpha", "bravo"):
                (Path(d) / name).mkdir()
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["--list"], specialisation_dir=d)
        self.assertEqual(rc, 0)
        lines = buf.getvalue().strip().splitlines()
        self.assertEqual(lines, ["alpha", "bravo"])

    def test_list_flag_empty_dir(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["--list"], specialisation_dir=d)
        self.assertEqual(rc, 0)
        self.assertIn("no specialisations found", buf.getvalue())

    def test_list_flag_does_not_call_runner(self) -> None:
        runner = CapturingRunner()
        with tempfile.TemporaryDirectory() as d:
            main(["--list"], runner=runner, specialisation_dir=d)
        self.assertEqual(len(runner.calls), 0)

    def test_help_exits(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            main(["--help"])
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()

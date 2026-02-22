from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from scripts_py.cli import rebuild_dispatch


class ExecCalled(RuntimeError):
    def __init__(self, argv: list[str]):
        super().__init__("exec called")
        self.argv = argv


def exec_capture(argv):
    raise ExecCalled(list(argv))


class TestRebuildDispatch(unittest.TestCase):
    def test_help_prints_usage(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = rebuild_dispatch.main(["--help"], exec_func=exec_capture)
        self.assertEqual(rc, 0)
        self.assertIn("usage: rebuild", out.getvalue().lower())

    def test_offline_without_offline_ok_errors(self):
        err = io.StringIO()
        with redirect_stderr(err):
            rc = rebuild_dispatch.main(
                ["--show-trace"],
                online_check=lambda: False,
                exec_func=exec_capture,
                env={},
                config_path=Path("/nonexistent.conf"),
            )
        self.assertEqual(rc, 2)
        self.assertIn("offline", err.getvalue().lower())

    def test_offline_with_offline_ok_execs_local_inner(self):
        with self.assertRaises(ExecCalled) as ctx:
            rebuild_dispatch.main(
                ["--offline-ok", "--show-trace"],
                online_check=lambda: False,
                exec_func=exec_capture,
                env={},
                config_path=Path("/nonexistent.conf"),
            )
        argv = ctx.exception.argv
        self.assertEqual(argv[:4], ["nix", "run", "/etc/nixos#rebuild-inner", "--"])
        self.assertIn("--offline-ok", argv)

    def test_dev_execs_rebuild_dev(self):
        with self.assertRaises(ExecCalled) as ctx:
            rebuild_dispatch.main(
                ["--dev", "--offline-ok"],
                online_check=lambda: True,
                exec_func=exec_capture,
                env={},
                config_path=Path("/nonexistent.conf"),
            )
        self.assertEqual(ctx.exception.argv[:2], ["rebuild-dev", "--dev"])

    def test_online_remote_success_returns_zero(self):
        rc = rebuild_dispatch.main(
            ["--show-trace"],
            online_check=lambda: True,
            run_remote=lambda argv: rebuild_dispatch.RunResult(0, "ok"),
            exec_func=exec_capture,
            env={},
            config_path=Path("/nonexistent.conf"),
        )
        self.assertEqual(rc, 0)

    def test_online_remote_networkish_failure_falls_back_when_offline_ok_default(self):
        with tempfile.TemporaryDirectory() as td:
            conf = Path(td) / "rebuild.conf"
            conf.write_text("[rebuild]\noffline_ok = true\n", encoding="utf-8")

            with self.assertRaises(ExecCalled) as ctx:
                rebuild_dispatch.main(
                    ["--show-trace"],
                    online_check=lambda: True,
                    run_remote=lambda argv: rebuild_dispatch.RunResult(
                        1,
                        (
                            "error: unable to download https://cache.nixos.org/x.narinfo: "
                            "Could not resolve hostname"
                        ),
                    ),
                    exec_func=exec_capture,
                    env={},
                    config_path=conf,
                )

            argv = ctx.exception.argv
            self.assertEqual(argv[:4], ["nix", "run", "/etc/nixos#rebuild-inner", "--"])

    def test_online_remote_non_network_failure_does_not_fall_back(self):
        rc = rebuild_dispatch.main(
            ["--offline-ok"],
            online_check=lambda: True,
            run_remote=lambda argv: rebuild_dispatch.RunResult(42, "syntax error"),
            exec_func=exec_capture,
            env={},
            config_path=Path("/nonexistent.conf"),
        )
        self.assertEqual(rc, 42)


if __name__ == "__main__":
    unittest.main()

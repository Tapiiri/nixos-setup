from __future__ import annotations

import io
import unittest
from collections.abc import Sequence

from scripts_py.cli.ts_connect import (
    DEFAULT_OP_ITEM_REF,
    build_op_read_argv,
    build_tailscale_ip_argv,
    build_tailscale_up_argv,
    connect,
    fetch_authkey,
    main,
    parse_tailscale_ip,
)


class CapturingRunner:
    """Test double that records calls and returns pre-configured values."""

    def __init__(
        self,
        return_codes: list[int] | None = None,
        outputs: list[tuple[int, str]] | None = None,
    ) -> None:
        self._codes = iter(return_codes or [])
        self._outputs = iter(outputs or [])
        self.calls: list[list[str]] = []
        self.output_calls: list[list[str]] = []

    def run(self, argv: Sequence[str]) -> int:
        self.calls.append(list(argv))
        return next(self._codes)

    def run_output(self, argv: Sequence[str]) -> tuple[int, str]:
        self.output_calls.append(list(argv))
        return next(self._outputs)


def noop_sleep(_: float, /) -> None:
    pass


class TestBuildArgvHelpers(unittest.TestCase):
    def test_op_read_uses_item_ref(self) -> None:
        argv = build_op_read_argv("op://Vault/item/field")
        self.assertEqual(argv, ["op", "read", "op://Vault/item/field"])

    def test_tailscale_up_includes_authkey(self) -> None:
        argv = build_tailscale_up_argv("tskey-auth-abc123", "nixos-installer")
        self.assertEqual(argv[0], "tailscale")
        self.assertIn("up", argv)
        self.assertIn("--authkey=tskey-auth-abc123", argv)

    def test_tailscale_up_includes_hostname(self) -> None:
        argv = build_tailscale_up_argv("tskey-auth-abc123", "my-host")
        self.assertIn("--hostname=my-host", argv)

    def test_tailscale_ip_uses_ipv4(self) -> None:
        argv = build_tailscale_ip_argv()
        self.assertEqual(argv[0], "tailscale")
        self.assertIn("ip", argv)
        self.assertIn("-4", argv)


class TestParseTailscaleIp(unittest.TestCase):
    def test_extracts_ip_from_output(self) -> None:
        self.assertEqual(parse_tailscale_ip("100.64.0.1\n"), "100.64.0.1")

    def test_strips_whitespace(self) -> None:
        self.assertEqual(parse_tailscale_ip("  100.64.0.1  \n"), "100.64.0.1")

    def test_returns_first_line(self) -> None:
        self.assertEqual(parse_tailscale_ip("100.64.0.1\nfd7a::1\n"), "100.64.0.1")

    def test_returns_none_for_empty_output(self) -> None:
        self.assertIsNone(parse_tailscale_ip(""))

    def test_returns_none_for_blank_lines(self) -> None:
        self.assertIsNone(parse_tailscale_ip("\n\n"))


class TestFetchAuthkey(unittest.TestCase):
    def test_returns_authkey_on_success(self) -> None:
        runner = CapturingRunner(outputs=[(0, "tskey-auth-abc123\n")])
        key = fetch_authkey(
            "op://Vault/item/field", runner,
            out=io.StringIO(), err=io.StringIO(),
        )
        self.assertEqual(key, "tskey-auth-abc123")

    def test_calls_op_read_with_item_ref(self) -> None:
        runner = CapturingRunner(outputs=[(0, "tskey-auth-abc123\n")])
        fetch_authkey(
            "op://MyVault/myitem/cred", runner,
            out=io.StringIO(), err=io.StringIO(),
        )
        self.assertEqual(runner.output_calls[0], ["op", "read", "op://MyVault/myitem/cred"])

    def test_returns_none_on_op_failure(self) -> None:
        runner = CapturingRunner(outputs=[(1, "")])
        err = io.StringIO()
        key = fetch_authkey(
            "op://Vault/item/field", runner,
            out=io.StringIO(), err=err,
        )
        self.assertIsNone(key)
        self.assertIn("ERROR", err.getvalue())
        self.assertIn("OP_SERVICE_ACCOUNT_TOKEN", err.getvalue())

    def test_returns_none_on_empty_key(self) -> None:
        runner = CapturingRunner(outputs=[(0, "  \n")])
        err = io.StringIO()
        key = fetch_authkey(
            "op://Vault/item/field", runner,
            out=io.StringIO(), err=err,
        )
        self.assertIsNone(key)
        self.assertIn("empty", err.getvalue())

    def test_strips_whitespace_from_key(self) -> None:
        runner = CapturingRunner(outputs=[(0, "  tskey-auth-abc  \n")])
        key = fetch_authkey(
            "op://Vault/item/field", runner,
            out=io.StringIO(), err=io.StringIO(),
        )
        self.assertEqual(key, "tskey-auth-abc")


class TestConnect(unittest.TestCase):
    def test_success_prints_ssh_info(self) -> None:
        runner = CapturingRunner(
            return_codes=[0],
            outputs=[(0, "100.64.0.1\n")],
        )
        out = io.StringIO()
        rc = connect(
            "tskey-auth-abc", "nixos-installer", runner,
            out=out, err=io.StringIO(), sleep=noop_sleep,
        )
        self.assertEqual(rc, 0)
        output = out.getvalue()
        self.assertIn("ssh root@100.64.0.1", output)
        self.assertIn("ssh root@nixos-installer", output)

    def test_tailscale_up_failure_returns_exit_code(self) -> None:
        runner = CapturingRunner(return_codes=[1], outputs=[])
        err = io.StringIO()
        rc = connect(
            "tskey-auth-abc", "nixos-installer", runner,
            out=io.StringIO(), err=err, sleep=noop_sleep,
        )
        self.assertEqual(rc, 1)
        self.assertIn("ERROR", err.getvalue())

    def test_ip_not_available_returns_error(self) -> None:
        runner = CapturingRunner(
            return_codes=[0],
            outputs=[(1, "")] * 3,
        )
        err = io.StringIO()
        rc = connect(
            "tskey-auth-abc", "nixos-installer", runner,
            out=io.StringIO(), err=err, retries=3, sleep=noop_sleep,
        )
        self.assertEqual(rc, 1)
        self.assertIn("ERROR", err.getvalue())

    def test_retries_until_ip_available(self) -> None:
        runner = CapturingRunner(
            return_codes=[0],
            outputs=[
                (1, ""),
                (1, ""),
                (0, "100.64.0.5\n"),
            ],
        )
        out = io.StringIO()
        rc = connect(
            "tskey-auth-abc", "nixos-installer", runner,
            out=out, err=io.StringIO(), retries=5, sleep=noop_sleep,
        )
        self.assertEqual(rc, 0)
        self.assertIn("100.64.0.5", out.getvalue())
        self.assertEqual(len(runner.output_calls), 3)

    def test_calls_sleep_between_retries(self) -> None:
        sleep_calls: list[float] = []
        runner = CapturingRunner(
            return_codes=[0],
            outputs=[(1, ""), (0, "100.64.0.1\n")],
        )
        connect(
            "tskey-auth-abc", "nixos-installer", runner,
            out=io.StringIO(), err=io.StringIO(), retries=5,
            sleep=sleep_calls.append,
        )
        self.assertEqual(sleep_calls, [1])

    def test_custom_hostname_in_output(self) -> None:
        runner = CapturingRunner(
            return_codes=[0],
            outputs=[(0, "100.64.0.1\n")],
        )
        out = io.StringIO()
        connect(
            "tskey-auth-abc", "my-installer", runner,
            out=out, err=io.StringIO(), sleep=noop_sleep,
        )
        self.assertIn("ssh root@my-installer", out.getvalue())


class TestMain(unittest.TestCase):
    def _make_runner(
        self,
        op_output: str = "tskey-auth-abc\n",
        op_rc: int = 0,
        ts_up_rc: int = 0,
        ts_ip_output: str = "100.64.0.1\n",
    ) -> CapturingRunner:
        """Create a runner for the full flow: op read -> tailscale up -> tailscale ip."""
        return CapturingRunner(
            return_codes=[ts_up_rc],
            outputs=[(op_rc, op_output), (0, ts_ip_output)],
        )

    def test_no_args_succeeds_with_defaults(self) -> None:
        runner = self._make_runner()
        rc = main(
            [], runner=runner,
            out=io.StringIO(), err=io.StringIO(), sleep=noop_sleep,
        )
        self.assertEqual(rc, 0)

    def test_fetches_from_1password_then_connects(self) -> None:
        runner = self._make_runner()
        rc = main(
            [], runner=runner,
            out=io.StringIO(), err=io.StringIO(), sleep=noop_sleep,
        )
        self.assertEqual(rc, 0)
        # First output call is op read, second is tailscale ip
        self.assertEqual(runner.output_calls[0][0], "op")
        self.assertIn("--authkey=tskey-auth-abc", runner.calls[0])

    def test_uses_default_op_item_ref(self) -> None:
        runner = self._make_runner()
        main(
            [], runner=runner,
            out=io.StringIO(), err=io.StringIO(), sleep=noop_sleep,
        )
        self.assertEqual(runner.output_calls[0], ["op", "read", DEFAULT_OP_ITEM_REF])

    def test_custom_item_ref(self) -> None:
        runner = self._make_runner()
        main(
            ["--item-ref", "op://Work/ts-key/password"], runner=runner,
            out=io.StringIO(), err=io.StringIO(), sleep=noop_sleep,
        )
        self.assertEqual(
            runner.output_calls[0],
            ["op", "read", "op://Work/ts-key/password"],
        )

    def test_custom_hostname(self) -> None:
        runner = self._make_runner()
        main(
            ["--hostname", "my-box"], runner=runner,
            out=io.StringIO(), err=io.StringIO(), sleep=noop_sleep,
        )
        self.assertIn("--hostname=my-box", runner.calls[0])

    def test_op_failure_returns_nonzero(self) -> None:
        runner = self._make_runner(op_rc=1, op_output="")
        rc = main(
            [], runner=runner,
            out=io.StringIO(), err=io.StringIO(), sleep=noop_sleep,
        )
        self.assertEqual(rc, 1)
        # Should not have called tailscale up
        self.assertEqual(len(runner.calls), 0)

    def test_default_hostname_is_nixos_installer(self) -> None:
        runner = self._make_runner()
        main(
            [], runner=runner,
            out=io.StringIO(), err=io.StringIO(), sleep=noop_sleep,
        )
        self.assertIn("--hostname=nixos-installer", runner.calls[0])


if __name__ == "__main__":
    unittest.main()

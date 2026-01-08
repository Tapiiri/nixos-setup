from __future__ import annotations

import io
import unittest

from scripts_py.update_github_env import (
    EnvLine,
    Gh,
    SimpleCompletedProcess,
    parse_env_text,
    update_from_pairs,
)


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], str | None]] = []
        self.next_returncodes: list[int] = []

    def run_capture(self, argv, *, input=None):  # type: ignore[no-untyped-def]
        self.calls.append((list(argv), input))
        rc = self.next_returncodes.pop(0) if self.next_returncodes else 0
        stderr = ""
        if rc != 0 and "api" in list(argv):
            stderr = "HTTP 404: Not Found"
        return SimpleCompletedProcess(returncode=rc, stdout="", stderr=stderr)


class TestParseEnvText(unittest.TestCase):
    def test_parses_and_sorts_and_dedups(self) -> None:
        txt = """
        # comment
        B=2
        A=1
        A=override
        EMPTY=
        """
        pairs = parse_env_text(txt)
        self.assertEqual(
            [(p.key, p.value) for p in pairs],
            [("A", "override"), ("B", "2"), ("EMPTY", "")],
        )

    def test_rejects_missing_equals(self) -> None:
        with self.assertRaises(ValueError):
            parse_env_text("NOPE")

    def test_rejects_bad_key(self) -> None:
        with self.assertRaises(ValueError):
            parse_env_text("9BAD=1")


class TestUpdateFromPairs(unittest.TestCase):
    def test_calls_gh_variable_and_secret(self) -> None:
        runner = FakeRunner()
        gh = Gh(runner=runner)
        out = io.StringIO()

        update_from_pairs(
            gh=gh,
            env="production",
            vars_pairs=[EnvLine("FOO", "bar")],
            secrets_pairs=[EnvLine("TOKEN", "secret")],
            repo=None,
            dry_run=False,
            out=out,
        )

        self.assertEqual(
            runner.calls,
            [
                (["gh", "variable", "set", "FOO", "--env", "production", "--body", "bar"], None),
                (["gh", "secret", "set", "TOKEN", "--env", "production"], "secret"),
            ],
        )

    def test_dry_run_skips_calls(self) -> None:
        runner = FakeRunner()
        gh = Gh(runner=runner)
        out = io.StringIO()

        update_from_pairs(
            gh=gh,
            env="production",
            vars_pairs=[EnvLine("FOO", "bar")],
            secrets_pairs=[EnvLine("TOKEN", "secret")],
            repo=None,
            dry_run=True,
            out=out,
        )

        self.assertEqual(runner.calls, [])


class TestEnsureEnvironment(unittest.TestCase):
    def test_noop_when_environment_exists(self) -> None:
        runner = FakeRunner()
        gh = Gh(runner=runner)

        gh.environment_ensure(env="production", repo=None)

        self.assertEqual(len(runner.calls), 1)
        argv, stdin = runner.calls[0]
        self.assertIsNone(stdin)
        self.assertEqual(argv[0:2], ["gh", "api"])

    def test_creates_when_missing(self) -> None:
        runner = FakeRunner()
        runner.next_returncodes = [1, 0]  # GET 404, then PUT ok
        gh = Gh(runner=runner)

        gh.environment_ensure(env="production", repo="OWNER/REPO")

        self.assertEqual(len(runner.calls), 2)
        get_argv, _ = runner.calls[0]
        put_argv, _ = runner.calls[1]

        self.assertIn("/environments/production", " ".join(get_argv))
        self.assertIn("/environments/production", " ".join(put_argv))
        self.assertIn("PUT", put_argv)


if __name__ == "__main__":
    unittest.main()

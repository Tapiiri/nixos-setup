"""Tests for scripts_py.cli.setup_github_pages."""

from __future__ import annotations

import unittest
from typing import Sequence

from scripts_py.cli.setup_github_pages import (
    CompletedProcess,
    Gh,
    PagesAction,
    PagesStatus,
    Runner,
    check_pages_status,
    parse_args,
    plan_pages_action,
)

# ---------------------------------------------------------------------------
# Fake runner for injecting API responses
# ---------------------------------------------------------------------------


class FakeRunner(Runner):
    """Records calls and returns canned responses."""

    def __init__(self, responses: list[CompletedProcess] | None = None) -> None:
        self.calls: list[list[str]] = []
        self._responses = list(responses or [])
        self._idx = 0

    def run_capture(self, argv: Sequence[str]) -> CompletedProcess:
        self.calls.append(list(argv))
        if self._idx < len(self._responses):
            resp = self._responses[self._idx]
            self._idx += 1
            return resp
        return CompletedProcess(returncode=0, stdout="{}", stderr="")


# ---------------------------------------------------------------------------
# PagesStatus
# ---------------------------------------------------------------------------


class TestPagesStatus(unittest.TestCase):
    def test_disabled_factory(self) -> None:
        s = PagesStatus.disabled()
        assert not s.enabled
        assert s.build_type == ""

    def test_from_api_workflow(self) -> None:
        s = PagesStatus.from_api(
            {"build_type": "workflow", "html_url": "https://example.github.io/repo/"}
        )
        assert s.enabled
        assert s.build_type == "workflow"
        assert s.url == "https://example.github.io/repo/"

    def test_from_api_legacy(self) -> None:
        s = PagesStatus.from_api({"build_type": "legacy"})
        assert s.enabled
        assert s.build_type == "legacy"


# ---------------------------------------------------------------------------
# plan_pages_action (pure logic)
# ---------------------------------------------------------------------------


class TestPlanPagesAction(unittest.TestCase):
    def test_enable_when_disabled(self) -> None:
        action = plan_pages_action(PagesStatus.disabled())
        assert action.kind == "enable"

    def test_noop_when_already_workflow(self) -> None:
        status = PagesStatus(enabled=True, build_type="workflow", url="https://x.io/")
        action = plan_pages_action(status)
        assert action.kind == "noop"

    def test_reconfigure_when_legacy(self) -> None:
        status = PagesStatus(enabled=True, build_type="legacy", url="https://x.io/")
        action = plan_pages_action(status)
        assert action.kind == "reconfigure"


# ---------------------------------------------------------------------------
# check_pages_status (with fake runner)
# ---------------------------------------------------------------------------


class TestCheckPagesStatus(unittest.TestCase):
    def test_returns_disabled_on_404(self) -> None:
        runner = FakeRunner([CompletedProcess(1, '{"message": "Not Found"}', "")])
        gh = Gh(runner=runner)
        status = check_pages_status(gh, "owner/repo")
        assert not status.enabled

    def test_returns_status_on_success(self) -> None:
        runner = FakeRunner(
            [
                CompletedProcess(
                    0,
                    '{"build_type": "workflow", "html_url": "https://owner.github.io/repo/"}',
                    "",
                )
            ]
        )
        gh = Gh(runner=runner)
        status = check_pages_status(gh, "owner/repo")
        assert status.enabled
        assert status.build_type == "workflow"

    def test_returns_disabled_on_non_dict_body(self) -> None:
        runner = FakeRunner([CompletedProcess(1, "some string", "")])
        gh = Gh(runner=runner)
        status = check_pages_status(gh, "owner/repo")
        assert not status.enabled


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------


class TestParseArgs(unittest.TestCase):
    def test_defaults(self) -> None:
        ns = parse_args([])
        assert ns.repo is None
        assert not ns.dry_run

    def test_repo_and_dry_run(self) -> None:
        ns = parse_args(["--repo", "owner/repo", "--dry-run"])
        assert ns.repo == "owner/repo"
        assert ns.dry_run


# ---------------------------------------------------------------------------
# apply_pages_action (noop path only — avoids real API calls)
# ---------------------------------------------------------------------------


class TestApplyPagesActionNoop(unittest.TestCase):
    def test_noop_returns_zero(self) -> None:
        import io

        from scripts_py.cli.setup_github_pages import apply_pages_action

        runner = FakeRunner([])
        gh = Gh(runner=runner)
        action = PagesAction(kind="noop", reason="already ok")
        out = io.StringIO()
        err = io.StringIO()
        rc = apply_pages_action(gh, "owner/repo", action, dry_run=False, out=out, err=err)
        assert rc == 0
        assert "already ok" in out.getvalue()

    def test_enable_dry_run(self) -> None:
        import io

        from scripts_py.cli.setup_github_pages import apply_pages_action

        runner = FakeRunner([])
        gh = Gh(runner=runner)
        action = PagesAction(kind="enable", reason="Pages is not enabled")
        out = io.StringIO()
        err = io.StringIO()
        rc = apply_pages_action(gh, "owner/repo", action, dry_run=True, out=out, err=err)
        assert rc == 0
        assert "dry-run" in out.getvalue()
        # No API calls should have been made.
        assert len(runner.calls) == 0

    def test_enable_real_call(self) -> None:
        import io

        from scripts_py.cli.setup_github_pages import apply_pages_action

        runner = FakeRunner([CompletedProcess(0, "", "")])
        gh = Gh(runner=runner)
        action = PagesAction(kind="enable", reason="Pages is not enabled")
        out = io.StringIO()
        err = io.StringIO()
        rc = apply_pages_action(gh, "owner/repo", action, dry_run=False, out=out, err=err)
        assert rc == 0
        assert len(runner.calls) == 1
        assert "-X" in runner.calls[0]
        assert "POST" in runner.calls[0]

    def test_enable_api_error(self) -> None:
        import io

        from scripts_py.cli.setup_github_pages import apply_pages_action

        runner = FakeRunner([CompletedProcess(1, "", "permission denied")])
        gh = Gh(runner=runner)
        action = PagesAction(kind="enable", reason="Pages is not enabled")
        out = io.StringIO()
        err = io.StringIO()
        rc = apply_pages_action(gh, "owner/repo", action, dry_run=False, out=out, err=err)
        assert rc == 1

    def test_reconfigure_uses_put(self) -> None:
        import io

        from scripts_py.cli.setup_github_pages import apply_pages_action

        runner = FakeRunner([CompletedProcess(0, "", "")])
        gh = Gh(runner=runner)
        action = PagesAction(kind="reconfigure", reason="switching source")
        out = io.StringIO()
        err = io.StringIO()
        rc = apply_pages_action(gh, "owner/repo", action, dry_run=False, out=out, err=err)
        assert rc == 0
        assert "PUT" in runner.calls[0]


if __name__ == "__main__":
    unittest.main()

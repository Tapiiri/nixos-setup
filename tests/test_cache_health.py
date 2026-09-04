# pyright: reportPrivateUsage=false
from __future__ import annotations

import io
import unittest
from pathlib import Path
from typing import Any

from scripts_py.lib import cache_health
from scripts_py.lib.cache_health import (
    CacheEntry,
    CacheIssue,
    HealthReport,
    check_all_caches,
    check_key_cachix,
    check_reachable,
    format_report,
    prompt_continue,
    run_preflight_check,
)

SAMPLE_CACHE = CacheEntry(
    id="nixCommunity",
    name="nix-community",
    url="https://nix-community.cachix.org",
    public_key="nix-community.cachix.org-1:mB9FSh9qf2dCimDSUo8Zy7bkq5CX+/rkCWyvRCYg3Fs=",
)

NON_CACHIX_CACHE = CacheEntry(
    id="forallSystems",
    name="forall-systems",
    url="https://cache.forall.systems",
    public_key="cache.forall.systems:5PmD7QO4MSF8YgyRZtkSGXRDo96H3bybIf2SsQh8ScI=",
)


class TestCheckReachable(unittest.TestCase):
    def test_reachable_returns_none(self) -> None:
        orig = cache_health._fetch_url

        def fake_fetch(url: str, *, timeout: float = 5.0) -> tuple[int, str]:
            self.assertEqual(url, "https://nix-community.cachix.org/nix-cache-info")
            return (200, "StoreDir: /nix/store\n")

        cache_health._fetch_url = fake_fetch  # type: ignore[assignment]
        try:
            result = check_reachable(SAMPLE_CACHE)
            self.assertIsNone(result)
        finally:
            cache_health._fetch_url = orig

    def test_unreachable_dns_failure(self) -> None:
        orig = cache_health._fetch_url
        cache_health._fetch_url = lambda url, *, timeout=5.0: (-1, "Name or service not known")  # type: ignore[assignment]
        try:
            result = check_reachable(SAMPLE_CACHE)
            assert result is not None
            self.assertEqual(result.kind, "unreachable")
            self.assertIn("Name or service not known", result.detail)
        finally:
            cache_health._fetch_url = orig

    def test_unreachable_http_error(self) -> None:
        orig = cache_health._fetch_url
        cache_health._fetch_url = lambda url, *, timeout=5.0: (503, "Service Unavailable")  # type: ignore[assignment]
        try:
            result = check_reachable(SAMPLE_CACHE)
            assert result is not None
            self.assertEqual(result.kind, "unreachable")
            self.assertIn("503", result.detail)
        finally:
            cache_health._fetch_url = orig


class TestCheckKeyCachix(unittest.TestCase):
    def test_key_matches(self) -> None:
        import json

        orig = cache_health._fetch_url
        cache_health._fetch_url = lambda url, *, timeout=5.0: (  # type: ignore[assignment]
            200,
            json.dumps({"publicSigningKeys": [SAMPLE_CACHE.public_key]}),
        )
        try:
            result = check_key_cachix(SAMPLE_CACHE)
            self.assertIsNone(result)
        finally:
            cache_health._fetch_url = orig

    def test_key_mismatch(self) -> None:
        import json

        orig = cache_health._fetch_url
        cache_health._fetch_url = lambda url, *, timeout=5.0: (  # type: ignore[assignment]
            200,
            json.dumps({"publicSigningKeys": ["nix-community.cachix.org-1:WRONGKEY=="]}),
        )
        try:
            result = check_key_cachix(SAMPLE_CACHE)
            assert result is not None
            self.assertEqual(result.kind, "key_mismatch")
            self.assertIn("WRONGKEY", result.detail)
            self.assertIn(SAMPLE_CACHE.public_key, result.detail)
        finally:
            cache_health._fetch_url = orig

    def test_api_unavailable_is_not_error(self) -> None:
        orig = cache_health._fetch_url
        cache_health._fetch_url = lambda url, *, timeout=5.0: (500, "Internal Server Error")  # type: ignore[assignment]
        try:
            result = check_key_cachix(SAMPLE_CACHE)
            self.assertIsNone(result)
        finally:
            cache_health._fetch_url = orig

    def test_non_cachix_url_skipped(self) -> None:
        result = check_key_cachix(NON_CACHIX_CACHE)
        self.assertIsNone(result)


class TestCheckAllCaches(unittest.TestCase):
    def test_aggregates_issues(self) -> None:
        issue = CacheIssue(cache=SAMPLE_CACHE, kind="unreachable", detail="DNS failed")
        orig = cache_health.check_cache
        cache_health.check_cache = lambda cache: [issue]  # type: ignore[assignment]
        try:
            report = check_all_caches([SAMPLE_CACHE])
            self.assertFalse(report.ok)
            self.assertEqual(len(report.issues), 1)
            self.assertEqual(report.issues[0].kind, "unreachable")
        finally:
            cache_health.check_cache = orig

    def test_no_issues_is_ok(self) -> None:
        orig = cache_health.check_cache
        cache_health.check_cache = lambda cache: []  # type: ignore[assignment]
        try:
            report = check_all_caches([SAMPLE_CACHE, NON_CACHIX_CACHE])
            self.assertTrue(report.ok)
        finally:
            cache_health.check_cache = orig


class TestFormatReport(unittest.TestCase):
    def test_ok_report_prints_nothing(self) -> None:
        buf = io.StringIO()
        format_report(HealthReport(), stderr=buf)
        self.assertEqual(buf.getvalue(), "")

    def test_issues_are_printed(self) -> None:
        report = HealthReport(
            issues=[
                CacheIssue(cache=SAMPLE_CACHE, kind="unreachable", detail="DNS failed"),
                CacheIssue(cache=NON_CACHIX_CACHE, kind="key_mismatch", detail="Key wrong"),
            ]
        )
        buf = io.StringIO()
        format_report(report, stderr=buf)
        output = buf.getvalue()
        self.assertIn("UNREACHABLE", output)
        self.assertIn("KEY MISMATCH", output)
        self.assertIn("nix-community", output)
        self.assertIn("forall-systems", output)
        self.assertIn("cachix-caches.nix", output)


class TestPromptContinue(unittest.TestCase):
    def test_yes(self) -> None:
        import builtins

        orig = builtins.input
        builtins.input = lambda prompt="": "y"  # type: ignore[assignment]
        try:
            self.assertTrue(prompt_continue(stderr=io.StringIO()))
        finally:
            builtins.input = orig  # type: ignore[assignment]

    def test_yes_full(self) -> None:
        import builtins

        orig = builtins.input
        builtins.input = lambda prompt="": "yes"  # type: ignore[assignment]
        try:
            self.assertTrue(prompt_continue(stderr=io.StringIO()))
        finally:
            builtins.input = orig  # type: ignore[assignment]

    def test_no(self) -> None:
        import builtins

        orig = builtins.input
        builtins.input = lambda prompt="": "n"  # type: ignore[assignment]
        try:
            self.assertFalse(prompt_continue(stderr=io.StringIO()))
        finally:
            builtins.input = orig  # type: ignore[assignment]

    def test_empty_is_no(self) -> None:
        import builtins

        orig = builtins.input
        builtins.input = lambda prompt="": ""  # type: ignore[assignment]
        try:
            self.assertFalse(prompt_continue(stderr=io.StringIO()))
        finally:
            builtins.input = orig  # type: ignore[assignment]

    def test_eof_is_no(self) -> None:
        import builtins

        orig = builtins.input

        def _raise(prompt: str = "") -> str:
            raise EOFError

        builtins.input = _raise  # type: ignore[assignment]
        try:
            self.assertFalse(prompt_continue(stderr=io.StringIO()))
        finally:
            builtins.input = orig  # type: ignore[assignment]

    def test_interrupt_is_no(self) -> None:
        import builtins

        orig = builtins.input

        def _raise(prompt: str = "") -> str:
            raise KeyboardInterrupt

        builtins.input = _raise  # type: ignore[assignment]
        try:
            self.assertFalse(prompt_continue(stderr=io.StringIO()))
        finally:
            builtins.input = orig  # type: ignore[assignment]


class TestRunPreflightCheck(unittest.TestCase):
    def test_no_caches_continues(self) -> None:
        orig = cache_health.load_caches_from_nix
        cache_health.load_caches_from_nix = lambda repo_root: []  # type: ignore[assignment]
        try:
            result = run_preflight_check(repo_root=Path("/tmp"), stderr=io.StringIO())
            self.assertTrue(result)
        finally:
            cache_health.load_caches_from_nix = orig

    def test_healthy_caches_continues(self) -> None:
        orig_load = cache_health.load_caches_from_nix
        orig_check = cache_health.check_all_caches
        orig_prompt = cache_health.prompt_continue
        prompt_called = {"n": 0}

        cache_health.load_caches_from_nix = lambda repo_root: [SAMPLE_CACHE]  # type: ignore[assignment]
        cache_health.check_all_caches = lambda caches: HealthReport()  # type: ignore[assignment]

        def _prompt(*, stderr: Any) -> bool:
            prompt_called["n"] += 1
            return False

        cache_health.prompt_continue = _prompt  # type: ignore[assignment]
        try:
            result = run_preflight_check(repo_root=Path("/tmp"), stderr=io.StringIO())
            self.assertTrue(result)
            self.assertEqual(prompt_called["n"], 0)
        finally:
            cache_health.load_caches_from_nix = orig_load
            cache_health.check_all_caches = orig_check
            cache_health.prompt_continue = orig_prompt

    def test_issues_prompt_abort(self) -> None:
        orig_load = cache_health.load_caches_from_nix
        orig_check = cache_health.check_all_caches
        orig_prompt = cache_health.prompt_continue

        cache_health.load_caches_from_nix = lambda repo_root: [SAMPLE_CACHE]  # type: ignore[assignment]
        cache_health.check_all_caches = lambda caches: HealthReport(  # type: ignore[assignment]
            issues=[CacheIssue(cache=SAMPLE_CACHE, kind="unreachable", detail="DNS")]
        )
        cache_health.prompt_continue = lambda *, stderr: False  # type: ignore[assignment]
        try:
            result = run_preflight_check(repo_root=Path("/tmp"), stderr=io.StringIO())
            self.assertFalse(result)
        finally:
            cache_health.load_caches_from_nix = orig_load
            cache_health.check_all_caches = orig_check
            cache_health.prompt_continue = orig_prompt

    def test_issues_prompt_continue(self) -> None:
        orig_load = cache_health.load_caches_from_nix
        orig_check = cache_health.check_all_caches
        orig_prompt = cache_health.prompt_continue

        cache_health.load_caches_from_nix = lambda repo_root: [SAMPLE_CACHE]  # type: ignore[assignment]
        cache_health.check_all_caches = lambda caches: HealthReport(  # type: ignore[assignment]
            issues=[CacheIssue(cache=SAMPLE_CACHE, kind="key_mismatch", detail="wrong")]
        )
        cache_health.prompt_continue = lambda *, stderr: True  # type: ignore[assignment]
        try:
            result = run_preflight_check(repo_root=Path("/tmp"), stderr=io.StringIO())
            self.assertTrue(result)
        finally:
            cache_health.load_caches_from_nix = orig_load
            cache_health.check_all_caches = orig_check
            cache_health.prompt_continue = orig_prompt


if __name__ == "__main__":
    unittest.main()

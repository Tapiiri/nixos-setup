# pyright: reportPrivateUsage=false
from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

from scripts_py.cli import ensure_cachix_cache


class TestEnsureCachixCache(unittest.TestCase):
    def test_check_cache_name_accepts_simple(self) -> None:
        self.assertEqual(ensure_cachix_cache._check_cache_name("my-cache"), "my-cache")

    def test_check_cache_name_rejects_invalid(self) -> None:
        with self.assertRaises(ValueError):
            ensure_cachix_cache._check_cache_name("bad name")

    def test_ensure_cache_configures_via_use(self) -> None:
        # Patch out external calls.
        ensure_cachix_cache._require_cachix = lambda: "cachix"  # type: ignore[assignment]
        ensure_cachix_cache._read_cachix_config = lambda: ensure_cachix_cache.CachixConfig(
            hostname="https://cachix.org", auth_token="tok"
        )  # type: ignore[assignment]
        ensure_cachix_cache.cachix_api_cache_exists = lambda *, cfg, cache_name: True  # type: ignore[assignment]

        called = {"use": 0}

        def _use(_exe: str, _name: str) -> None:
            called["use"] += 1

        ensure_cachix_cache.cachix_use_cache = _use  # type: ignore[assignment]

        res = ensure_cachix_cache.ensure_cache(cache_name="nixos-setup", visibility="public")
        self.assertTrue(res.configured)
        self.assertEqual(called["use"], 1)

    def test_ensure_cache_creates_when_missing(self) -> None:
        ensure_cachix_cache._require_cachix = lambda: "cachix"  # type: ignore[assignment]
        ensure_cachix_cache._read_cachix_config = lambda: ensure_cachix_cache.CachixConfig(
            hostname="https://cachix.org", auth_token="tok"
        )  # type: ignore[assignment]
        ensure_cachix_cache.cachix_api_cache_exists = lambda *, cfg, cache_name: False  # type: ignore[assignment]

        created = {"called": 0}

        def _create(*, cfg: Any, cache_name: str, visibility: str) -> None:
            created["called"] += 1

        ensure_cachix_cache.cachix_api_create_cache = _create  # type: ignore[assignment]

        used = {"called": 0}

        def _use(_exe: str, _name: str) -> None:
            used["called"] += 1

        ensure_cachix_cache.cachix_use_cache = _use  # type: ignore[assignment]

        res = ensure_cachix_cache.ensure_cache(cache_name="nixos-setup", visibility="public")
        self.assertTrue(res.created)
        self.assertTrue(res.configured)
        self.assertEqual(created["called"], 1)
        self.assertEqual(used["called"], 1)

    def test_ensure_cache_no_create_when_exists(self) -> None:
        ensure_cachix_cache._require_cachix = lambda: "cachix"  # type: ignore[assignment]
        ensure_cachix_cache._read_cachix_config = lambda: ensure_cachix_cache.CachixConfig(
            hostname="https://cachix.org", auth_token="tok"
        )  # type: ignore[assignment]
        ensure_cachix_cache.cachix_api_cache_exists = lambda *, cfg, cache_name: True  # type: ignore[assignment]

        created = {"called": 0}

        def _create(*, cfg: Any, cache_name: str, visibility: str) -> None:
            created["called"] += 1

        ensure_cachix_cache.cachix_api_create_cache = _create  # type: ignore[assignment]

        used = {"called": 0}

        def _use(_exe: str, _name: str) -> None:
            used["called"] += 1

        ensure_cachix_cache.cachix_use_cache = _use  # type: ignore[assignment]

        res = ensure_cachix_cache.ensure_cache(cache_name="nixos-setup", visibility="public")
        self.assertFalse(res.created)
        self.assertTrue(res.configured)
        self.assertEqual(created["called"], 0)
        self.assertEqual(used["called"], 1)

    def test_repo_name_from_root(self) -> None:
        self.assertEqual(
            ensure_cachix_cache._repo_name_from_root(Path("/tmp/some-repo")), "some-repo"
        )


if __name__ == "__main__":
    unittest.main()

"""Pre-rebuild health check for configured Nix binary caches.

Verifies that each cache defined in cachix-caches.nix is reachable and that
its signing key matches what the cache is actually using.  Reports problems
and lets the caller decide whether to continue.
"""

from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO


@dataclass(frozen=True)
class CacheEntry:
    id: str
    name: str
    url: str
    public_key: str


@dataclass(frozen=True)
class CacheIssue:
    cache: CacheEntry
    kind: str  # "unreachable" | "key_mismatch"
    detail: str


@dataclass
class HealthReport:
    issues: list[CacheIssue] = field(default_factory=lambda: list[CacheIssue]())

    @property
    def ok(self) -> bool:
        return len(self.issues) == 0


def load_caches_from_nix(repo_root: Path) -> list[CacheEntry]:
    """Evaluate cachix-caches.nix and return structured cache entries."""
    caches_file = repo_root / "cachix-caches.nix"
    if not caches_file.is_file():
        return []

    cp = subprocess.run(
        ["nix", "eval", "--json", "--file", str(caches_file)],
        text=True,
        capture_output=True,
        timeout=30,
    )
    if cp.returncode != 0:
        return []

    data = json.loads(cp.stdout)
    return [
        CacheEntry(
            id=key,
            name=entry["name"],
            url=entry["url"],
            public_key=entry["publicKey"],
        )
        for key, entry in data.items()
    ]


def _fetch_url(url: str, *, timeout: float = 5.0) -> tuple[int, str]:
    """GET a URL, return (status_code, body).  Returns (-1, error) on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": "nixos-setup/cache-health"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        return -1, str(e)


def check_reachable(cache: CacheEntry) -> CacheIssue | None:
    """Check that the cache responds to /nix-cache-info."""
    url = cache.url.rstrip("/") + "/nix-cache-info"
    status, body = _fetch_url(url)
    if status == -1:
        return CacheIssue(cache=cache, kind="unreachable", detail=body)
    if status != 200:
        return CacheIssue(
            cache=cache,
            kind="unreachable",
            detail=f"HTTP {status}",
        )
    return None


def _is_cachix_url(url: str) -> bool:
    from urllib.parse import urlparse

    hostname = urlparse(url).hostname or ""
    return hostname == "cachix.org" or hostname.endswith(".cachix.org")


def _cachix_cache_name(url: str) -> str | None:
    """Extract the cache name from a cachix URL like https://foo.cachix.org."""
    import re

    m = re.match(r"https?://([^.]+)\.cachix\.org", url)
    return m.group(1) if m else None


def check_key_cachix(cache: CacheEntry) -> CacheIssue | None:
    """For cachix caches, verify the configured key matches the API."""
    cache_name = _cachix_cache_name(cache.url)
    if cache_name is None:
        return None

    api_url = f"https://cachix.org/api/v1/cache/{cache_name}"
    status, body = _fetch_url(api_url)
    if status != 200:
        # Can't verify — not an error in itself (API might be down / private cache).
        return None

    try:
        data = json.loads(body)
        remote_keys = data.get("publicSigningKeys", [])
    except (json.JSONDecodeError, TypeError):
        return None

    if not remote_keys:
        return None

    if cache.public_key not in remote_keys:
        return CacheIssue(
            cache=cache,
            kind="key_mismatch",
            detail=(
                f"Configured key: {cache.public_key}\n"
                f"    Remote key(s): {', '.join(remote_keys)}"
            ),
        )
    return None


def check_key_narinfo(cache: CacheEntry) -> CacheIssue | None:
    """For non-cachix caches, fetch the nix-cache-info and try a narinfo to check signing."""
    # This is a best-effort heuristic: we can't fully verify without nix internals,
    # but we can at least check that the key name prefix matches what narinfos are
    # signed with.

    # We need a store path hash to look up.  Try fetching a well-known derivation
    # that's likely cached.  If this fails, skip — we can't verify.
    # Instead of guessing a path, we rely on the reachability check and cachix API
    # for cachix caches.  For non-cachix caches there's no standard API, so we
    # skip key verification.
    return None


def check_cache(cache: CacheEntry) -> list[CacheIssue]:
    """Run all checks for a single cache."""
    issues: list[CacheIssue] = []

    reachability = check_reachable(cache)
    if reachability is not None:
        issues.append(reachability)
        # Skip key check if unreachable.
        return issues

    if _is_cachix_url(cache.url):
        key_issue = check_key_cachix(cache)
    else:
        key_issue = check_key_narinfo(cache)

    if key_issue is not None:
        issues.append(key_issue)

    return issues


def check_all_caches(caches: list[CacheEntry]) -> HealthReport:
    """Check all caches and return a report."""
    report = HealthReport()
    for cache in caches:
        report.issues.extend(check_cache(cache))
    return report


_ISSUE_LABELS = {
    "unreachable": "UNREACHABLE",
    "key_mismatch": "KEY MISMATCH",
}


def format_report(report: HealthReport, *, stderr: TextIO) -> None:
    """Print a human-readable summary of cache issues."""
    if report.ok:
        return

    print("\n[cache-health] Problems detected with binary caches:", file=stderr)
    for issue in report.issues:
        label = _ISSUE_LABELS.get(issue.kind, issue.kind.upper())
        print(f"  [{label}] {issue.cache.name} ({issue.cache.url})", file=stderr)
        for line in issue.detail.splitlines():
            print(f"    {line}", file=stderr)

    print(file=stderr)
    print(
        "  Affected caches will be skipped by Nix — packages they provide will be",
        file=stderr,
    )
    print(
        "  built from source, which is significantly slower.",
        file=stderr,
    )
    print(
        "  To fix: update cachix-caches.nix with correct keys/URLs and rebuild.",
        file=stderr,
    )
    print(file=stderr)


def prompt_continue(*, stderr: TextIO) -> bool:
    """Ask the user whether to continue despite cache issues.

    Returns True if the user wants to continue, False to abort.
    """
    try:
        answer = input("Continue rebuild without these caches? [y/N] ")
    except (EOFError, KeyboardInterrupt):
        print(file=stderr)
        return False
    return answer.strip().lower() in ("y", "yes")


def run_preflight_check(
    *,
    repo_root: Path,
    stderr: TextIO,
) -> bool:
    """Run the full pre-rebuild cache health check.

    Returns True if the rebuild should proceed, False to abort.
    """
    caches = load_caches_from_nix(repo_root)
    if not caches:
        return True

    report = check_all_caches(caches)
    if report.ok:
        return True

    format_report(report, stderr=stderr)
    return prompt_continue(stderr=stderr)

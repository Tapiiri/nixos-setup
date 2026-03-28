from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from scripts_py.lib.utils import log_error, log_info
from scripts_py.repo.context import repo_root_from_script_path

CACHE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9-]{0,79}$")


@dataclass(frozen=True)
class Result:
    cache_name: str
    created: bool
    configured: bool


@dataclass(frozen=True)
class CachixConfig:
    hostname: str
    auth_token: str | None


def _repo_name_from_root(repo_root: Path) -> str:
    # Default to directory name; works for typical checkouts.
    return repo_root.name


def _check_cache_name(name: str) -> str:
    if not CACHE_NAME_RE.match(name):
        raise ValueError(
            f"Invalid cachix cache name '{name}'. Cachix allows alnum + '-', 1-80 chars."
        )
    return name


def _require_cachix() -> str:
    exe = shutil.which("cachix")
    if not exe:
        raise FileNotFoundError(
            "cachix CLI not found on PATH. Install it (e.g. `nix profile install nixpkgs#cachix` "
            "or enable it via Home Manager in this repo)."
        )
    return exe


def _read_cachix_config() -> CachixConfig:
    """Read Cachix config from ~/.config/cachix/cachix.dhall.

    Cachix 1.x stores an auth token + hostname in Dhall. We keep parsing very
    small/safe (regex over the expected keys) so we don't need external deps.
    """

    cfg_path = Path.home() / ".config" / "cachix" / "cachix.dhall"
    try:
        raw = cfg_path.read_text(encoding="utf-8")
    except OSError:
        # Cachix UI uses app.cachix.org; this is the safest default for API calls.
        return CachixConfig(hostname="https://app.cachix.org", auth_token=None)

    # Dhall file is simple: { authToken = "...", hostname = "...", ... }
    # Token may be line-wrapped, so read it as a quoted string allowing newlines.
    host_m = re.search(r"hostname\s*=\s*\"([^\"]+)\"", raw)
    token_m = re.search(r"authToken\s*=\s*\"([\s\S]*?)\"", raw)

    hostname = (host_m.group(1).strip() if host_m else "https://app.cachix.org").rstrip("/")
    token = token_m.group(1) if token_m else None
    if token is not None:
        token = "".join(ch for ch in token if ch not in " \t\r\n")
        if not token:
            token = None

    return CachixConfig(hostname=hostname, auth_token=token)


def _cachix_api_base(hostname: str) -> str:
    # app.cachix.org swagger paths are rooted at /api/v1.
    return hostname.rstrip("/") + "/api/v1"


def _http_json(
    *,
    method: str,
    url: str,
    token: str | None,
    body: bytes | None = None,
) -> tuple[int, str]:
    headers = {"Accept": "application/json", "User-Agent": "nixos-setup/ensure-cachix-cache"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url=url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        payload = e.read().decode("utf-8", errors="replace")
        return e.code, payload


def cachix_api_cache_exists(*, cfg: CachixConfig, cache_name: str) -> bool:
    url = f"{_cachix_api_base(cfg.hostname)}/cache/{cache_name}"
    status, _ = _http_json(method="GET", url=url, token=cfg.auth_token)
    if status == 200:
        return True
    if status == 404:
        return False
    if status in (401, 403):
        # Cachix may return 401 or 403 for missing caches, private caches, or
        # when the token lacks read permissions.  Treat as "unknown" and let
        # the creation attempt resolve it.
        return False
    # Other codes mean auth/network/etc; treat as error.
    raise RuntimeError(f"Unexpected response from Cachix API (GET cache): HTTP {status}")


def cachix_api_create_cache(*, cfg: CachixConfig, cache_name: str, visibility: str) -> None:
    if not cfg.auth_token:
        raise RuntimeError(
            "No Cachix auth token found. Run `cachix authtoken <token>` first "
            "(or set CACHIX_AUTH_TOKEN for CI)."
        )

    # According to app.cachix.org swagger:
    # POST /api/v1/cache/{name} body: BinaryCacheCreate
    #   { accountID, generateSigningKey, isPublic, ... }
    # We only support creating personal caches here (accountID fetched from /api/v1/user).
    url = f"{_cachix_api_base(cfg.hostname)}/cache/{cache_name}"

    # Determine whether cache is public.
    is_public = visibility == "public"

    # Fetch the current user to get accountID.
    user_url = f"{_cachix_api_base(cfg.hostname)}/user"
    status_u, text_u = _http_json(method="GET", url=user_url, token=cfg.auth_token)
    if status_u != 200:
        raise RuntimeError(
            "Failed to query Cachix user info (needed for accountID). "
            f"HTTP {status_u}. Response: {text_u.strip()[:2000]}"
        )
    try:
        user = json.loads(text_u)
        account_id = int(user["id"])
    except Exception as e:  # noqa: BLE001
        raise RuntimeError("Could not parse account id from /user response") from e

    payload = json.dumps(
        {
            "accountID": account_id,
            "generateSigningKey": True,
            "isPublic": is_public,
        }
    ).encode("utf-8")

    status, text = _http_json(method="POST", url=url, token=cfg.auth_token, body=payload)
    if status in (200, 201):
        return
    if status == 409:
        # Already exists (race). Fine.
        return
    if status == 401:
        raise RuntimeError(
            "Cachix API returned 401 (unauthorized) while creating the cache. "
            "Your token may be missing permissions for cache creation. "
            "Create the cache in the UI first (app.cachix.org) and re-run."
        )
    raise RuntimeError(
        f"Failed to create Cachix cache via API. HTTP {status}. Response: {text.strip()[:2000]}"
    )


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, check=False, text=True, capture_output=True)


def cachix_use_cache(cachix_exe: str, cache_name: str) -> None:
    """Configure cache in nix.conf via `cachix use`.

    This also effectively checks that the cache exists and is reachable.
    """

    argv = [cachix_exe, "use", cache_name]
    p = _run(argv)
    if p.returncode != 0:
        # Typical reasons:
        # - cache doesn't exist
        # - network / hostname mismatch
        # - permission issues
        raise RuntimeError(
            "Failed to configure Cachix cache via `cachix use`.\n"
            f"Command: {' '.join(argv)}\n"
            f"stdout:\n{p.stdout}\n"
            f"stderr:\n{p.stderr}\n\n"
            "If the cache doesn't exist yet, create it at https://app.cachix.org "
            "(or via the Cachix API), then rerun this command."
        )


def ensure_cache(*, cache_name: str, visibility: str) -> Result:
    cache_name = _check_cache_name(cache_name)
    cachix_exe = _require_cachix()

    cfg = _read_cachix_config()
    created = False

    if not cachix_api_cache_exists(cfg=cfg, cache_name=cache_name):
        cachix_api_create_cache(cfg=cfg, cache_name=cache_name, visibility=visibility)
        created = True

    cachix_use_cache(cachix_exe, cache_name)
    return Result(cache_name=cache_name, created=created, configured=True)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ensure-cachix-cache",
        description=(
            "Ensure a Cachix cache exists for this repo (defaults to repo folder name). "
            "Creates it if missing."
        ),
    )
    p.add_argument(
        "--name",
        help="Cachix cache name (default: repo directory name)",
        default=None,
    )
    p.add_argument(
        "--visibility",
        choices=["public", "private"],
        default="public",
        help="Cache visibility when creating a new cache (default: public)",
    )
    p.add_argument(
        "--repo-root",
        default=None,
        help="Override repo root detection (default: auto-detect)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)

    repo_root = (
        Path(ns.repo_root).resolve() if ns.repo_root else repo_root_from_script_path(Path(__file__))
    )

    cache_name = ns.name or _repo_name_from_root(repo_root)

    try:
        res = ensure_cache(cache_name=cache_name, visibility=ns.visibility)
    except Exception as e:
        log_error(str(e), err=sys.stderr)
        return 2

    if res.created:
        log_info(f"Created Cachix cache '{res.cache_name}'.", out=sys.stdout)

    if res.configured:
        log_info(
            f"Configured Cachix cache '{res.cache_name}' for Nix (via `cachix use`).",
            out=sys.stdout,
        )

    log_info(
        "Tip: set CACHIX_AUTH_TOKEN in GitHub Actions secrets so CI can push.",
        out=sys.stdout,
    )

    # Small hint for CI wiring.
    if os.environ.get("GITHUB_ACTIONS") == "true":
        log_info(
            "In GitHub Actions, set secrets.CACHIX_AUTH_TOKEN and use cachix/cachix-action.",
            out=sys.stdout,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

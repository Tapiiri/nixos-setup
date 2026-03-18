"""Attestation cache for ``nix flake check --no-build``.

Hashes all ``.nix`` files and ``flake.lock`` in the repo to produce a
composite fingerprint.  When the pre-commit hook runs, it can skip the
(slow) ``nix flake check`` entirely if nothing Nix-related changed since
the last passing run.

The on-disk format and storage location are identical to the test
attestation cache in ``test_attestation.py``, so the same GC/invalidation
tools apply.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

# Subdirectory under the devenv state dir.
CACHE_DIR_NAME = "nix-check-attestations"

# How long a cached result stays valid.
DEFAULT_MAX_AGE_S = 86400.0  # 24 h

# File patterns that form the input set for ``nix flake check``.
_NIX_GLOB = "**/*.nix"
_EXTRA_FILES: tuple[str, ...] = ("flake.lock",)

# Directories to exclude from scanning (devenv internals, build results).
_EXCLUDED_DIRS: frozenset[str] = frozenset({".devenv", "result"})


# ------------------------------------------------------------------
# Hashing
# ------------------------------------------------------------------


def _file_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return "MISSING"


def _is_excluded(path: Path, repo_root: Path) -> bool:
    """Return True if *path* sits under an excluded directory."""
    try:
        rel = path.relative_to(repo_root)
    except ValueError:
        return True
    return any(part in _EXCLUDED_DIRS for part in rel.parts)


def compute_nix_hash(repo_root: Path) -> str:
    """SHA-256 fingerprint of every ``.nix`` file + ``flake.lock``."""
    parts: list[str] = []

    nix_files = sorted(
        p for p in repo_root.glob(_NIX_GLOB) if p.is_file() and not _is_excluded(p, repo_root)
    )
    for nf in nix_files:
        rel = nf.relative_to(repo_root)
        parts.append(f"nix:{rel}:{_file_sha256(nf)}")

    for extra in sorted(_EXTRA_FILES):
        ef = repo_root / extra
        parts.append(f"extra:{extra}:{_file_sha256(ef)}")

    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


# ------------------------------------------------------------------
# Storage
# ------------------------------------------------------------------


def _cache_dir(state_dir: Path) -> Path:
    d = state_dir / CACHE_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_path(state_dir: Path, nix_hash: str) -> Path:
    return _cache_dir(state_dir) / f"nix-flake-{nix_hash[:16]}.json"


def store_nix_attestation(
    state_dir: Path,
    nix_hash: str,
    *,
    ok: bool,
    elapsed: float = 0.0,
) -> Path:
    """Write a nix-check attestation record."""
    data = {
        "nix_hash": nix_hash,
        "ok": ok,
        "ts": time.time(),
        "elapsed": elapsed,
    }
    p = _cache_path(state_dir, nix_hash)
    p.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    return p


def lookup_nix_attestation(
    state_dir: Path,
    nix_hash: str,
    *,
    max_age_s: float = DEFAULT_MAX_AGE_S,
) -> bool | None:
    """Look up a cached nix-check result.

    Returns ``True`` (pass), ``False`` (fail), or ``None`` (miss/expired).
    """
    p = _cache_path(state_dir, nix_hash)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if time.time() - data.get("ts", 0) > max_age_s:
        return None
    return data.get("ok")


def invalidate_nix_attestations(state_dir: Path) -> int:
    """Remove all nix-check attestations.  Returns count removed."""
    d = _cache_dir(state_dir)
    count = 0
    for p in d.glob("*.json"):
        p.unlink(missing_ok=True)
        count += 1
    return count


def gc_nix_stale(state_dir: Path, *, max_age_s: float = DEFAULT_MAX_AGE_S) -> int:
    """Remove nix-check attestations older than *max_age_s*."""
    d = _cache_dir(state_dir)
    now = time.time()
    count = 0
    for p in d.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            p.unlink(missing_ok=True)
            count += 1
            continue
        if now - data.get("ts", 0) > max_age_s:
            p.unlink(missing_ok=True)
            count += 1
    return count

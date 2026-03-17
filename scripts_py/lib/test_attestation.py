"""File-level test result caching.

Caches pass/fail results per test file, keyed by a composite hash of the test
file plus all of its transitive internal dependencies and global config files.
When the pre-commit hook runs, it can skip pytest entirely if every affected
test already has a fresh passing attestation.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from scripts_py.lib.depmap import GLOBAL_CONFIG_FILES, transitive_deps

# Default subdirectory under the devenv state dir.
CACHE_DIR_NAME = "test-attestations"

# Attestations older than this are ignored.
DEFAULT_MAX_AGE_S = 86400.0  # 24 h


# ------------------------------------------------------------------
# Data model
# ------------------------------------------------------------------


@dataclass(frozen=True)
class FileAttestation:
    """On-disk record for a single test file's last result."""

    test_file: str
    deps_hash: str
    ok: bool
    ts: float
    elapsed: float = 0.0


# ------------------------------------------------------------------
# Hashing
# ------------------------------------------------------------------


def _file_sha256(path: Path) -> str:
    """Return hex SHA-256 of a file's bytes, or a sentinel for missing files."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return "MISSING"


def compute_composite_hash(
    test_file: Path,
    deps: set[Path],
    repo_root: Path,
) -> str:
    """Compute a single SHA-256 that covers *test_file*, its deps, and global configs.

    The hash changes whenever any input file's content changes.
    """
    parts: list[str] = []

    # Test file itself.
    parts.append(f"test:{_file_sha256(test_file)}")

    # Sorted deps for determinism.
    for dep in sorted(deps):
        parts.append(f"dep:{_file_sha256(dep)}")

    # Global config files.
    for cfg_name in sorted(GLOBAL_CONFIG_FILES):
        cfg_path = repo_root / cfg_name
        parts.append(f"cfg:{cfg_name}:{_file_sha256(cfg_path)}")

    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------
# Storage helpers
# ------------------------------------------------------------------


def _cache_dir(state_dir: Path) -> Path:
    d = state_dir / CACHE_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_key(test_file: Path, composite_hash: str) -> str:
    """Filename-safe cache key: ``<test_stem>-<hash_prefix>.json``."""
    return f"{test_file.stem}-{composite_hash[:16]}.json"


def store_attestation(
    state_dir: Path,
    test_file: Path,
    composite_hash: str,
    *,
    ok: bool,
    elapsed: float = 0.0,
) -> Path:
    """Write an attestation record and return the path written."""
    att = FileAttestation(
        test_file=str(test_file),
        deps_hash=composite_hash,
        ok=ok,
        ts=time.time(),
        elapsed=elapsed,
    )
    p = _cache_dir(state_dir) / _cache_key(test_file, composite_hash)
    p.write_text(json.dumps(asdict(att), sort_keys=True), encoding="utf-8")
    return p


def lookup_attestation(
    state_dir: Path,
    test_file: Path,
    composite_hash: str,
    *,
    max_age_s: float = DEFAULT_MAX_AGE_S,
) -> bool | None:
    """Look up a cached result for *test_file* at *composite_hash*.

    Returns:
        ``True``  — cached pass
        ``False`` — cached fail
        ``None``  — no record (or expired)
    """
    p = _cache_dir(state_dir) / _cache_key(test_file, composite_hash)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    ts = data.get("ts", 0)
    if time.time() - ts > max_age_s:
        return None
    return data.get("ok")


def check_all_attested(
    state_dir: Path,
    test_files: set[Path],
    graph: dict[Path, set[Path]],
    repo_root: Path,
    *,
    max_age_s: float = DEFAULT_MAX_AGE_S,
) -> tuple[set[Path], set[Path]]:
    """Partition *test_files* into ``(attested, unattested)`` sets.

    A test file is *attested* if it has a passing attestation whose composite
    hash matches the file's current dependencies.
    """
    attested: set[Path] = set()
    unattested: set[Path] = set()
    for tf in test_files:
        deps = transitive_deps(graph, tf)
        ch = compute_composite_hash(tf, deps, repo_root)
        result = lookup_attestation(state_dir, tf, ch, max_age_s=max_age_s)
        if result is True:
            attested.add(tf)
        else:
            unattested.add(tf)
    return attested, unattested


def invalidate_all(state_dir: Path) -> int:
    """Remove every cached attestation.  Returns count of files removed."""
    d = _cache_dir(state_dir)
    count = 0
    for p in d.glob("*.json"):
        p.unlink(missing_ok=True)
        count += 1
    return count


def gc_stale(state_dir: Path, *, max_age_s: float = DEFAULT_MAX_AGE_S) -> int:
    """Remove attestations older than *max_age_s*.  Returns count removed."""
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

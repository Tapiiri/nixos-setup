from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable

GLOB_CHARS_RE = re.compile(r"[\\*\\?\\[]")


def is_glob_pattern(pattern: str) -> bool:
    return bool(GLOB_CHARS_RE.search(pattern)) or "**" in pattern


def normalize_posix(path: str) -> str:
    # SchemaStore fileMatch globs are slash-separated.
    return path.replace("\\\\", "/")


def match_filematch(path: str, pattern: str) -> bool:
    """Match a repo-relative path against a SchemaStore fileMatch pattern.

    SchemaStore patterns are mostly glob-like. In practice they contain:
    - basenames like "appveyor.yml" (match anywhere)
    - path globs like "**/.github/workflows/*.yml"

    We support these via:
    - PurePosixPath.match for patterns containing '/'
    - fnmatch-like semantics on basename for patterns without '/'

    Note: some SchemaStore patterns use extended glob syntax (e.g. !(config)).
    We intentionally treat those as unsupported and return False.
    """

    path = normalize_posix(path)
    pattern = normalize_posix(pattern)

    # Reject extglob patterns which PurePosixPath.match does not support.
    if "!(" in pattern or "@(" in pattern or "+(" in pattern or "*(" in pattern or "?(" in pattern:
        return False

    p = PurePosixPath(path)

    if "/" not in pattern:
        # Match against the basename.
        return p.name == pattern or PurePosixPath(p.name).match(pattern)

    # Normalize patterns like "/foo/bar.yml" to "foo/bar.yml".
    while pattern.startswith("/"):
        pattern = pattern[1:]

    if p.match(pattern):
        return True

    # PurePosixPath.match treats a leading "**/" as requiring at least one
    # directory segment. SchemaStore globs commonly use "**/" to mean "any
    # parent dirs (including zero)", so we also try without the prefix.
    if pattern.startswith("**/"):
        return p.match(pattern[3:])

    return False


def pattern_specificity(pattern: str) -> tuple[int, int, int, int, str]:
    """Deterministic 'most specific' sort key.

    Higher is better for the numeric parts.
    """

    pattern = normalize_posix(pattern)

    # Non-glob beats glob.
    exact = 1 if not is_glob_pattern(pattern) else 0

    wildcard_count = pattern.count("*") + pattern.count("?")
    double_star_count = pattern.count("**")

    # Prefer fewer wildcards / fewer **.
    fewer_wildcards = -wildcard_count
    fewer_double_stars = -double_star_count

    # Prefer longer patterns (tend to be more specific).
    length = len(pattern)

    return (exact, fewer_double_stars, fewer_wildcards, length, pattern)


def best_matching_pattern(path: str, patterns: Iterable[str]) -> str | None:
    matches: list[str] = [p for p in patterns if match_filematch(path, p)]
    if not matches:
        return None
    return sorted(matches, key=pattern_specificity, reverse=True)[0]


@dataclass(frozen=True)
class CatalogSchema:
    name: str
    url: str
    description: str | None
    file_match: tuple[str, ...]


def choose_schema_for_file(
    path: str,
    schemas: Iterable[CatalogSchema],
) -> tuple[CatalogSchema, str] | None:
    """Return (schema, matching_pattern) chosen deterministically."""

    candidates: list[tuple[tuple[int, int, int, int, str], CatalogSchema, str]] = []

    for schema in schemas:
        pat = best_matching_pattern(path, schema.file_match)
        if not pat:
            continue
        candidates.append((pattern_specificity(pat), schema, pat))

    if not candidates:
        return None

    candidates.sort(
        key=lambda t: (
            t[0],
            t[1].name,
            t[1].url,
        ),
        reverse=True,
    )
    _score, schema, pat = candidates[0]
    return (schema, pat)


def schema_cache_filename(schema_url: str) -> str:
    """Stable local filename for a schema URL."""

    digest = hashlib.sha256(schema_url.encode("utf-8")).hexdigest()[:20]
    return f"{digest}.json"


def dump_json(obj: object) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

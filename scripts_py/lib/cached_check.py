"""Generic command-result caching by input file hash.

Given a check name, a set of input globs/files, and a command to run,
this module:

1. Computes a composite SHA-256 over all matching input files.
2. Looks up whether the same hash already has a stored pass/fail.
3. If cache hit (pass) → returns immediately.
4. If miss → runs the command, stores the result, returns the exit code.

This is the shared engine behind all cached pre-commit hooks (nix flake
check, pytest, ruff, pyright, yamllint, shellcheck, etc.).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

# Default attestation lifetime.
DEFAULT_MAX_AGE_S = 86400.0  # 24 h

# Directories always excluded from glob scanning.
_EXCLUDED_DIRS: frozenset[str] = frozenset({".devenv", "result", ".git", "__pycache__", "site"})


# ------------------------------------------------------------------
# Data model
# ------------------------------------------------------------------


@dataclass(frozen=True)
class CheckAttestation:
    """On-disk record for a single check's last result."""

    name: str
    input_hash: str
    ok: bool
    ts: float
    elapsed: float = 0.0


# ------------------------------------------------------------------
# Hashing
# ------------------------------------------------------------------


def _file_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return "MISSING"


def _is_excluded(path: Path, repo_root: Path) -> bool:
    try:
        rel = path.relative_to(repo_root)
    except ValueError:
        return True
    return any(part in _EXCLUDED_DIRS for part in rel.parts)


def compute_input_hash(
    repo_root: Path,
    *,
    globs: tuple[str, ...] = (),
    files: tuple[str, ...] = (),
) -> str:
    """Composite SHA-256 of all files matching *globs* + explicit *files*.

    Globs are resolved relative to *repo_root*.  Excluded directories
    (``.devenv``, ``result``, ``.git``, ``__pycache__``, ``site``) are
    skipped automatically.
    """
    parts: list[str] = []

    # Expand globs.
    for pattern in sorted(globs):
        matched = sorted(
            p for p in repo_root.glob(pattern) if p.is_file() and not _is_excluded(p, repo_root)
        )
        for f in matched:
            rel = f.relative_to(repo_root)
            parts.append(f"glob:{pattern}:{rel}:{_file_sha256(f)}")

    # Explicit files.
    for fname in sorted(files):
        fp = repo_root / fname
        parts.append(f"file:{fname}:{_file_sha256(fp)}")

    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------
# Storage
# ------------------------------------------------------------------


def _cache_dir(state_dir: Path, name: str) -> Path:
    d = state_dir / f"{name}-attestations"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_path(state_dir: Path, name: str, input_hash: str) -> Path:
    return _cache_dir(state_dir, name) / f"{name}-{input_hash[:16]}.json"


def store(
    state_dir: Path,
    name: str,
    input_hash: str,
    *,
    ok: bool,
    elapsed: float = 0.0,
) -> Path:
    """Write an attestation record and return the path written."""
    att = CheckAttestation(
        name=name,
        input_hash=input_hash,
        ok=ok,
        ts=time.time(),
        elapsed=elapsed,
    )
    p = _cache_path(state_dir, name, input_hash)
    p.write_text(json.dumps(asdict(att), sort_keys=True), encoding="utf-8")
    return p


def lookup(
    state_dir: Path,
    name: str,
    input_hash: str,
    *,
    max_age_s: float = DEFAULT_MAX_AGE_S,
) -> bool | None:
    """Look up a cached result.

    Returns ``True`` (pass), ``False`` (fail), or ``None`` (miss/expired).
    """
    p = _cache_path(state_dir, name, input_hash)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if time.time() - data.get("ts", 0) > max_age_s:
        return None
    return data.get("ok")


def invalidate(state_dir: Path, name: str) -> int:
    """Remove all attestations for *name*.  Returns count removed."""
    d = _cache_dir(state_dir, name)
    count = 0
    for p in d.glob("*.json"):
        p.unlink(missing_ok=True)
        count += 1
    return count


def gc_stale(state_dir: Path, name: str, *, max_age_s: float = DEFAULT_MAX_AGE_S) -> int:
    """Remove attestations for *name* older than *max_age_s*."""
    d = _cache_dir(state_dir, name)
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


# ------------------------------------------------------------------
# Check registry — declares inputs for each named check
# ------------------------------------------------------------------


@dataclass(frozen=True)
class CheckDef:
    """Declares the input-file scope for a named check.

    *ci_check* marks entries that correspond to a ``check:all`` leaf task.
    Formatter-only entries (``fmt:*``) set ``ci_check=False`` — they
    participate in pre-commit caching but are **not** required by
    ``verify_local_attestations``.
    """

    name: str
    globs: tuple[str, ...] = ()
    files: tuple[str, ...] = ()
    ci_check: bool = True


# Every check that participates in the generic caching system.
KNOWN_CHECKS: tuple[CheckDef, ...] = (
    CheckDef(
        name="check-flake-lock",
        files=("flake.nix", "flake.lock"),
        # Pure Python check — verifies flake.lock has entries for all flake.nix inputs.
    ),
    CheckDef(
        name="nix-flake-check",
        globs=("**/*.nix",),
        files=("flake.lock",),
        # Evaluates nixosConfigurations.base + packages — CI-safe (no private inputs).
    ),
    CheckDef(
        name="nix-host-fw12",
        globs=("**/*.nix",),
        files=("flake.lock",),
        ci_check=False,  # local-only — requires private vaisala-pilot input
    ),
    CheckDef(
        name="nix-host-fw16",
        globs=("**/*.nix",),
        files=("flake.lock",),
        ci_check=False,  # local-only — requires private vaisala-pilot input
    ),
    CheckDef(
        name="pytest",
        globs=("scripts_py/**/*.py", "tests/**/*.py"),
        files=("pyproject.toml", "devenv.nix"),
    ),
    CheckDef(
        name="ruff",
        globs=("scripts_py/**/*.py", "tests/**/*.py"),
        files=("pyproject.toml",),
    ),
    CheckDef(
        name="pyright",
        globs=("scripts_py/**/*.py", "tests/**/*.py"),
        files=("pyproject.toml",),
    ),
    CheckDef(
        name="alejandra",
        globs=("**/*.nix",),
        ci_check=False,  # fmt:nix:alejandra — not in check:all
    ),
    CheckDef(
        name="yamllint",
        globs=("**/*.yml", "**/*.yaml"),
        files=(".yamllint",),
    ),
    CheckDef(
        name="actionlint",
        globs=(".github/workflows/**/*.yml", ".github/workflows/**/*.yaml"),
    ),
    CheckDef(
        name="shellcheck",
        globs=("**/*.sh",),
        files=("dotfiles/home/bashrc",),
    ),
    CheckDef(
        name="shfmt",
        globs=("**/*.sh",),
        files=("dotfiles/home/bashrc",),
        ci_check=False,  # fmt:shell:shfmt — not in check:all
    ),
    CheckDef(
        name="taplo-check",
        globs=("**/*.toml",),
    ),
    CheckDef(
        name="taplo-fmt",
        globs=("**/*.toml",),
        ci_check=False,  # fmt:toml:taplo — not in check:all
    ),
    CheckDef(
        name="jq-fmt",
        globs=("**/*.json",),
        ci_check=False,  # fmt:json:jq — not in check:all
    ),
    CheckDef(
        name="markdownlint",
        globs=("**/*.md",),
        files=(".markdownlint-cli2.yaml",),
    ),
    CheckDef(
        name="schemastore",
        globs=("**/*.yml", "**/*.yaml", "**/*.json"),
        files=("schemas/schemastore-index.json",),
    ),
    CheckDef(
        name="mkdocs",
        globs=("docs/site/**",),
        files=("mkdocs.yml",),
    ),
)

CHECKS_BY_NAME: dict[str, CheckDef] = {c.name: c for c in KNOWN_CHECKS}

# Subset required by verify_local_attestations (matches check:all leaves).
CI_CHECKS: tuple[CheckDef, ...] = tuple(c for c in KNOWN_CHECKS if c.ci_check)


def lookup_named(
    state_dir: Path,
    repo_root: Path,
    name: str,
    *,
    max_age_s: float = DEFAULT_MAX_AGE_S,
) -> bool | None:
    """Convenience: compute the current input hash for a registered check and look it up."""
    check = CHECKS_BY_NAME.get(name)
    if check is None:
        return None
    h = compute_input_hash(repo_root, globs=check.globs, files=check.files)
    return lookup(state_dir, name, h, max_age_s=max_age_s)

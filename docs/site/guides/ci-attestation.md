# CI & Attestation

This repo implements a **local attestation system** using git notes that lets
you skip redundant CI runs when you've already verified your changes locally.

## Concept

When you run the full CI-equivalent check locally, the system writes a
cryptographic attestation (as a git note) recording that the commit passed.
On push, GitHub Actions checks for this note and can skip re-running the
same checks.

```text
Local machine                        GitHub Actions
─────────────                        ──────────────
1. Run checks locally
2. attest-ci-checks writes           3. ci-attestation-gate reads
   git note on HEAD                      git note for the commit
3. Push (includes notes)             4. Attestation found?
                                        ├─ yes → skip checks
                                        └─ no  → run full CI
```

!!! note
    This is a convenience for personal/solo workflows. Git notes are not a strong
    security boundary — PRs from others still run CI normally.

## Scripts involved

| Script | Purpose |
|--------|---------|
| `attest-ci-checks` | Run a devenv task and write a git-notes attestation |
| `check-ci-attestation` | Check whether a commit has a successful attestation |
| `ci-attestation-gate` | Decide whether CI can be skipped; writes `$GITHUB_OUTPUT` |

## Writing an attestation

After running all checks locally:

```bash
scripts/attest-ci-checks --task check:all --push
```

This:

1. Runs `devenv tasks run -m all check:all`
2. If it succeeds, writes a git note recording the success
3. `--push` pushes the notes ref to the remote

## The post-commit hook

A `post-commit` hook (set up by devenv / pre-commit) automates attestation:

1. After each commit, it checks if pre-commit ran successfully via `--verify-local`
2. If pre-commit passed → writes the attestation automatically
3. If pre-commit was skipped (`git commit --no-verify`) → no attestation, CI runs normally

## Pre-commit caching layer

Two scripts add fine-grained caching on top of the attestation system:

### `cached-nix-check`

Runs `nix flake check --no-build` with attestation caching:

- Hashes all `.nix` files + `flake.lock` to compute a cache key
- If the key matches a previous successful run → skip
- Otherwise → run the check and cache the result

### `cached-pytest`

Runs pytest with **file-level** attestation caching:

- Uses the AST-based dependency map (`scripts_py/lib/depmap.py`) to determine
  which test files are affected by changes
- Only re-runs tests whose dependencies have changed
- Caches pass/fail per test file, keyed by a composite hash of the file and its
  transitive imports

This means editing a utility module only re-runs the tests that actually import
it, not the entire test suite.

## GitHub Actions integration

The CI workflow uses `ci-attestation-gate` to check for attestations:

1. The gate script reads git notes for the pushed commit
2. If a valid attestation exists → sets a GitHub Actions output to skip checks
3. If no attestation → CI proceeds normally

The gate is conservative: any doubt results in running CI.

## Architecture

```text
┌─────────────────────────────────────────────────────────┐
│ scripts_py/ci/                                          │
│   attest_ci_checks.py    — write attestation notes      │
│   check_ci_attestation.py — read/verify attestation     │
│   ci_attestation_gate.py — GitHub Actions gate logic    │
├─────────────────────────────────────────────────────────┤
│ scripts_py/lib/                                         │
│   nix_check_attestation.py — hash .nix files for cache  │
│   test_attestation.py      — per-file test result cache │
│   depmap.py                — AST import graph for tests │
└─────────────────────────────────────────────────────────┘
```

## Limitations

- Git notes must be pushed explicitly (`--push` flag or hook config)
- Notes can be lost if the remote's notes ref is force-pushed
- The system trusts the local machine — it doesn't verify *how* the checks ran
- Only useful for direct pushes to `main`; PRs from forks always run CI

## Merge commits and `pre-merge-commit` hooks

Since Git 2.24, `git merge` triggers the `pre-merge-commit` hook **instead of**
the `pre-commit` hook.  If pre-merge-commit is not installed, merges that bring
in changes to `.nix` files, `flake.lock`, or Python sources silently skip all
pre-commit checks — leaving the attestation caches stale.

The post-commit hook (which **does** run after merge commits) then calls
`verify_local_attestations()`, finds the stale caches, and refuses to write the
git-notes attestation.  The result: CI runs the full check suite even though
the developer is working inside the devenv environment.

**Fix in this repo:** `git-hooks.default_stages` in `devenv.nix` is set to
`["pre-commit" "pre-merge-commit"]`, ensuring all hooks run in both stages.
When devenv detects a hook using the `pre-merge-commit` stage, it automatically
installs `.git/hooks/pre-merge-commit` on the next `devenv shell` entry.

!!! warning
    If you see attestation failures after `git pull`, re-enter the devenv shell
    (`devenv shell`) to ensure `.git/hooks/pre-merge-commit` is installed.
    You can verify with: `ls -la .git/hooks/pre-merge-commit`

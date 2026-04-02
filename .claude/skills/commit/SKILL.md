---
name: commit
description: Create a git commit in this repo with full awareness of the devenv hook chain. Verifies check:all is passing, stages files, commits, and handles any hook failures by diagnosing and fixing rather than bypassing.
allowed-tools: Bash, Read, Edit, Write, Grep, Glob
---

Commit changes in this repo, respecting the hook chain. Never bypass hooks with `--no-verify`.

## Step 1: Verify devenv shell

```bash
echo "${DEVENV_ROOT:-NOT_IN_DEVENV}"
```

If the output is `NOT_IN_DEVENV`, stop and tell the user:
> You need to be inside the devenv shell — pre-commit hooks use pinned tooling from devenv. Run `devenv shell` first.

## Step 2: Understand current state

Run these in parallel to get a full picture:

```bash
git status
```
```bash
git diff --staged
```
```bash
git diff
```
```bash
git log --oneline -5
```

## Step 3: Verify checks are passing

Before committing, the attestation caches must be fresh so the post-commit hook can write a CI attestation. If you haven't already run `/check`, run it now:

```bash
devenv tasks run -m all check:all
```

If `check:all` fails, fix the failures first (see `/check` skill). Do not commit broken code.

## Step 4: Stage files

Stage specific files rather than `git add -A` to avoid accidentally including sensitive files or unrelated changes:

```bash
git add <specific files>
```

Review what is staged before committing:
```bash
git diff --staged
```

## Step 5: Commit

Write a commit message that explains **why**, not just what. Follow the style of recent commits (seen in step 2). Use a HEREDOC to avoid shell quoting issues:

```bash
git commit -m "$(cat <<'EOF'
Short summary (imperative mood, ≤72 chars)

Optional longer explanation if the change is non-obvious.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

## Step 6: Handle hook failures

### Pre-commit hook failures (cached checks)
Pre-commit runs cached checks. If a check fails here but passed in step 3, something changed between check:all and now. Read the error, fix the issue, re-stage, and try again. Do **not** use `--no-verify`.

### Post-commit hook failures (`attest-ci-checks --verify-local`)
The post-commit hook verifies that all attestation caches are fresh before writing a git-notes CI attestation.

**If it fails with "check(s) not attested":** The caches are stale (e.g. after `git merge` that changed `.nix` files or `flake.lock`). The hook auto-recovers by running `check:all` — wait for it to finish. If it still fails after auto-recovery, check the error output and diagnose.

**If it fails for another reason:** Read the error carefully. The post-commit hook failure does not undo the commit — it just means CI will run the full pipeline for this commit instead of skipping.

### Pre-push hook (`attest-ci-checks --push-only`)
The pre-push hook pushes the git-notes attestation ref to origin (best-effort). Failure here is logged but never blocks the push.

## Step 7: Confirm

```bash
git log --oneline -3
git status
```

Report what was committed and the current state of the working tree.

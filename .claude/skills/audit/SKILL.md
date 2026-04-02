---
name: audit
description: Run the tooling coverage audit to verify all file types in the repo have linters, formatters, and VS Code extensions configured. Identify and address unmuted gaps. Use when asked to audit tooling coverage or check for uncovered file types.
allowed-tools: Bash, Read, Edit, Write, Grep, Glob
---

Run the tooling coverage audit and address any gaps.

## Step 1: Run the audit

```bash
devenv tasks run audit:tooling
```

This produces a coverage matrix: for each file type present in the repo, it shows whether linters, formatters, and VS Code extensions are configured. Gaps are file types that lack coverage.

## Step 2: Check for unmuted gaps (strict mode)

```bash
devenv tasks run audit:tooling:strict
```

Exit code 0 = no unmuted gaps. Exit code 1 = unmuted gaps exist and need attention.

## Step 3: Evaluate each gap

For each unmuted gap, decide:

**Fix it** — if the file type genuinely needs tooling that's missing:
- Add a `cachedCheck` entry to `devenv.nix`. One entry generates the pre-commit hook, background watcher process, and devenv task simultaneously (single source of truth).
- Follow the existing pattern in `devenv.nix`. Each entry needs: `cacheName`, `globs`, `cmd`, `hook` (key, name, files pattern), `process` (or null), and `task` (key, description).
- Add the tool itself to `packages` in `devenv.nix` if not already present.
- Run `devenv tasks run -m all check:all` to verify the new check passes.

**Mute it** — if the gap is acceptable (e.g. a file type that doesn't benefit from tooling, or tooling is handled elsewhere):
- Find the muting mechanism in the tooling registry at `scripts_py/lib/tooling_audit.py`
- Add an appropriate mute entry with a comment explaining why it's acceptable.

## Step 4: Re-run to confirm

```bash
devenv tasks run audit:tooling:strict
```

Should exit 0 after all gaps are fixed or muted.

## Step 5: Run check:all

After any changes to `devenv.nix` or `scripts_py/`:

```bash
devenv tasks run -m all check:all
```

Verify the new checks pass and nothing existing was broken.

## Notes

The audit-tooling script was specifically built to discover gaps that aren't obvious — it previously led to pyright being added. Treat unmuted gaps as potential quality improvements, not noise.

---
name: check
description: Run the full CI-equivalent check pipeline (check:all) inside devenv shell, interpret any failures, and fix them. Use when asked to run checks, verify the repo is clean, or before committing.
allowed-tools: Bash, Read, Edit, Write, Grep, Glob
---

Run the full check pipeline for this repo. Fix any failures before reporting done.

## Step 1: Verify devenv shell

```bash
echo "${DEVENV_ROOT:-NOT_IN_DEVENV}"
```

If the output is `NOT_IN_DEVENV`, stop and tell the user:
> You need to be inside the devenv shell for checks to use the correct pinned tooling. Run `devenv shell` first.

## Step 2: Run check:all

```bash
devenv tasks run -m all check:all
```

This is the single authoritative pipeline:
- `check:nix:flake` — Nix evaluation (`nix flake check --no-build`)
- `lint:python:ruff` — Python linting
- `lint:python:pyright` — Python type checking (strict)
- `lint:shell:shellcheck` — Shell script linting
- `lint:yaml:yamllint` — YAML linting
- `lint:schemastore:validate` — Schema validation
- `lint:gha:actionlint` — GitHub Actions workflow linting
- `lint:md:markdownlint` — Markdown linting
- `lint:toml:taplo` — TOML linting
- `tests:python:pytest` — Python test suite
- `docs:mkdocs:build` — Docs build (strict mode)

Results are **cached by input file hash** — if the relevant files haven't changed since the last passing run, the check is skipped instantly.

## Step 3: Interpret and fix failures

If any check fails, read the output carefully and fix the root cause — don't just silence errors.

**Common fixes:**

- **ruff**: Run `devenv tasks run -m all fmt:all` first (fixes formatting automatically), then re-run `check:all` to see remaining lint issues
- **pyright**: Fix the type annotation or the implementation — never add `# type: ignore` without a comment explaining why
- **pytest**: Read the failing test and the implementation together, fix the bug in the implementation (not the test, unless the test expectation is wrong)
- **markdownlint**: Run `devenv tasks run fmt:md:markdownlint` to auto-fix most issues
- **nix-flake-check**: Read the Nix error output carefully; fix the expression in `flake.nix` or the relevant `.nix` file
- **alejandra / shfmt / taplo / jq-fmt**: Formatting only — run `devenv tasks run -m all fmt:all`
- **actionlint / yamllint**: Fix the workflow or YAML file at the flagged line
- **schemastore**: Validate the flagged file against its schema; fix the structure

After each fix, re-run the specific failing task first (faster feedback):
```bash
devenv tasks run lint:python:ruff        # or whichever failed
```
Then re-run `check:all` to confirm everything is green.

## Step 4: Report

Summarise what happened:
- Which checks passed (note whether they were cache hits or fresh runs)
- What was broken and what was changed to fix it
- Final state: all green, or what remains and why

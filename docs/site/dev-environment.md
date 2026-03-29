# Dev Environment

This repo pins all development tooling in `devenv.nix` and exposes canonical
checks as **devenv tasks** — the single source of truth for local development,
pre-commit hooks, and CI.

## Entering the dev shell

```bash
devenv shell
```

This gives you a shell with all pinned tools (Python 3.13, pytest, ruff, mkdocs,
pre-commit, etc.) available on `$PATH`.

!!! tip "VS Code integration"
    Prefer launching VS Code via the repo's wrapper `scripts/code` (installed by
    `setup-links`). It detects `devenv.nix` and runs VS Code inside the devenv
    shell, so GUI git commits and hooks use the same tooling.

## Task system

Devenv tasks are the **single source of truth** for all checks. Pre-commit hooks
and CI both delegate to these tasks.

### Common entrypoints

| Command | What it runs |
|---------|-------------|
| `devenv tasks run -m all check:all` | Full CI-equivalent pipeline |
| `devenv tasks run -m all lint:all` | All linters |
| `devenv tasks run -m all fmt:all` | All formatters |
| `devenv tasks run tests:python:pytest` | Python test suite |
| `devenv tasks run lint:python:ruff` | Python linter (ruff) |
| `devenv tasks run check:nix:flake` | Nix flake check |
| `devenv tasks run docs:mkdocs:build` | Build docs (strict mode) |
| `devenv tasks run docs:mkdocs:serve` | Local docs preview server |

### Task hierarchy

```text
check:all
├── check:nix:flake
├── lint:all
│   ├── lint:python:ruff
│   └── (other linters)
├── tests:all
│   └── tests:python:pytest
└── docs:all
    └── docs:mkdocs:build
```

## Pre-commit hooks

Pre-commit hooks wrap the devenv tasks, ensuring local checks match CI exactly.
Run them manually:

```bash
pre-commit run --all-files
```

!!! warning "Run inside devenv"
    Always run pre-commit inside the devenv shell so the PATH and tool versions
    match CI. Outside devenv, hooks may fail with "command not found" errors.

## Python setup

Two "modes" are supported:

### Devenv (recommended)

`devenv.nix` pins Python (currently 3.13) plus `pytest` and `ruff`.
Everything is available after `devenv shell`.

### Minimal / stdlib-only

Tests are written so they can run with the stdlib `unittest` when needed:

```bash
python -m unittest -q
```

If `pytest` is installed, prefer the module form to avoid PATH/interpreter
mismatches:

```bash
python -m pytest -q
```

!!! note
    Avoid introducing new Python deps lightly. Dev deps belong in `devenv.nix`;
    "real" tooling deps are managed via Home Manager (`home/modules/devtools.nix`).

## Local docs preview

Build the docs site:

```bash
devenv tasks run docs:mkdocs:build
```

Start a local preview server (auto-reloads on changes):

```bash
devenv tasks run docs:mkdocs:serve
```

Then open <http://127.0.0.1:8000> in your browser.

## CI pipeline

CI runs the same tasks as local development. On push to `main`, GitHub Actions
executes:

```bash
devenv tasks run -m all check:all
```

### Skipping CI with attestation

If you've already run the full check locally, the
[CI attestation system](guides/ci-attestation.md) can skip the redundant run in
GitHub Actions. See that guide for details.

# Copilot instructions for this repo

## What this repo is

- NixOS + Home Manager flake repo. The system flake is `./flake.nix` and host configs live under `hosts/`.
- This repo also ships small, *tested* helper CLIs: shell wrappers in `scripts/` with Python implementations in `scripts_py/`.

## Key workflows (use these exact flows)

- Dev tooling (Python + linters + pre-commit) is pinned in `./devenv.nix` (devenv.sh).
  - Prefer running checks inside the devenv shell so PATH/tooling matches CI.
  - Enter dev shell:
    - `devenv shell`
- Canonical checks live in **devenv tasks** (single source of truth):
  - Full CI-equivalent pipeline:
    - `devenv shell -- devenv tasks run check:all`
  - Targeted checks (prefer these when appropriate):
    - Python lint: `devenv shell -- devenv tasks run lint:python:ruff`
    - Python tests: `devenv shell -- devenv tasks run tests:python:pytest`
    - Nix evaluation: `devenv shell -- devenv tasks run check:nix:flake`
    - All lint: `devenv shell -- devenv tasks run lint:all`
    - All format: `devenv shell -- devenv tasks run fmt:all`
- Pre-commit is a local convenience layer and delegates hook logic to devenv tasks:
  - `devenv shell -- pre-commit run --all-files`

## Architecture & conventions

### Scripts layout

- User-facing executables: `scripts/<name>` (often symlinked into `~/.local/bin` via `scripts/setup-links`).
- Testable implementation modules: `scripts_py/<name>.py`.
- Shared utilities: `scripts_py/utils.py`.
  - Conventions worth following:
    - Repo root detection uses `repo_root_from_script_path()` and markers (`flake.nix` + `scripts_py/`).
    - Prefer `Path` objects and explicit, user-friendly error messages.

### VS Code + devenv integration

- Prefer launching VS Code via the repo’s wrapper `scripts/code` (installed by `scripts/setup-links`).
  - It walks up from the folder you open; if it finds `devenv.nix`, it runs `code ...` *inside* the devenv shell.
  - This keeps GUI git commits / hooks running with the same tooling as the devenv environment.

### `rebuild` (system-critical)

- The `rebuild` wrapper (`scripts_py/rebuild.py`) is designed around a **root-owned** `/etc/nixos` checkout plus an optional **local bare mirror**:
  - Defaults: flake source `/etc/nixos`, mirror `/var/lib/nixos-setup/mirror.git`.
  - Mirror sync is **default** when not using `--dev`.
  - `--dev` uses the current repo checkout as the flake source.
  - `--offline-ok` allows continuing when fetch fails; in `--dev` mode it may push local `main` to the mirror as an offline fallback.
- When changing anything in `rebuild`, preserve these flows and their safety properties (root/user separation).

### Home Manager modules

- Home Manager modules live under `home/modules/` and features under `home/features/`.
- VS Code feature is intentionally split into:
  - managed/structural settings in `home/features/vscode/default.nix`
  - runtime-mutable settings in `home/features/vscode/user-settings.nix` (updated by `scripts/sync-vscode-settings`)

### Flake outputs / host naming

- Host configs are addressed as `.<#hostname>` in `nixos-rebuild --flake ...`.
  - Example (see `flake.nix`): `nixosConfigurations.nixos = ...`.
  - Keep this in sync with `hosts/<hostname>/` and the machine hostname.

### Flake outputs / profiles debugging tip

- This flake intentionally exposes `nixosConfigurations.<host>` but may **not** expose
  `homeConfigurations.*` as a top-level flake output.
- When you need to discover what outputs exist (or when a build target is unclear), run:
  - `nix flake show --all-systems`
- When you specifically need to *force evaluation* of Home Manager modules (for example
  to surface a VS Code Marketplace extension hash mismatch), a reliable target is:
  - `.#nixosConfigurations.<host>.config.system.build.toplevel`

This avoids guesswork around “profiles” / output names and matches how we actually build
the system configuration.

## Editing guidelines specific to this repo

- Avoid introducing new Python deps lightly: dev deps belong in `devenv.nix`; “real” tooling deps are managed via Home Manager (`home/modules/devtools.nix`, referenced in `README.md`).
- Keep scripts runnable in minimal environments; tests should remain able to run with stdlib `unittest`.
- Prefer modifying Python implementation in `scripts_py/` and keep `scripts/` wrappers thin.

## Where to look for examples

- Mirror + /etc/nixos flake workflow: `README.md` and `scripts_py/rebuild.py`.
- Repo root/path bootstrapping patterns: `scripts_py/utils.py`.
- VS Code settings sync: `home/features/vscode/README.md` and `scripts_py/sync_vscode_settings.py`.

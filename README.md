# nixos-setup

A personal NixOS + Home Manager flake repo, plus a small set of **tested helper CLIs** that make daily workflows predictable:

- **Mirror-based `/etc/nixos` flow** (root doesn’t need network access)
- **Devenv-pinned dev tooling** (CI + pre-commit use the same tasks)
- **Hybrid VS Code settings**: declarative “structural” settings + runtime-mutable preferences
- **Repo utilities** in `scripts/` with Python implementations in `scripts_py/` and unit tests in `tests/`

If you’re new to this repo: start with the quickstart below, then skim the sections for the piece you need.

## Quickstart

### 1) Get the repo scripts on PATH

This repo ships user-facing executables under `scripts/`. The intended way to use them is to link them to `~/.local/bin`:

- `./scripts/setup-links`

Notes:

- The linker is conservative: it only links **user-owned** targets; root-owned targets are skipped.
- If `rebuild` (or other scripts) “aren’t found”, see [PATH troubleshooting](#path-troubleshooting).

### 2) Run the main workflows

- Rebuild your system (recommended daily entrypoint):
  - `rebuild`
- Sync VS Code runtime settings back into Nix (optional, for multi-machine preferences):
  - `sync-vscode-settings`

## Repository layout

High-level structure and “where things live”:

- `flake.nix` / `flake.lock`: flake entrypoint + inputs
- `hosts/<hostname>/`: per-host NixOS configuration (`configuration.nix`, `hardware-configuration.nix`, and optional `home.nix`)
- `home/modules/`: reusable Home Manager modules (enabled via host configs)
- `home/features/`: higher-level feature bundles (example: VS Code)
- `scripts/`: user-facing CLI wrappers (designed to be runnable as normal executables)
- `scripts_py/`: Python implementations (testable, imported by wrappers)
- `tests/`: unit tests for scripts
- `docs/`: focused deep-dives (VS Code settings, extension packaging, etc.)

## Dev environment, CI, and the “source of truth” tasks

This repo pins dev tooling in `devenv.nix` and exposes canonical checks as **devenv tasks**.

These tasks are the single source of truth for:

- local development
- pre-commit hooks
- CI checks

Common entrypoints:

- Full CI-equivalent pipeline:
  - `devenv shell -- devenv tasks run check:all`
- Lint:
  - `devenv shell -- devenv tasks run lint:all`
- Format:
  - `devenv shell -- devenv tasks run fmt:all`
- Python tests:
  - `devenv shell -- devenv tasks run tests:python:pytest`

### Secretspec + LastPass login (common gotcha)

This repo enables `secretspec` in `devenv`. If the LastPass CLI (`lpass`) is not
logged in, `devenv` can fail in a way that looks opaque.

To make this actionable, the pre-commit hooks that call `devenv tasks ...` now
run a small preflight (`scripts/ensure-lpass-login`) first and will tell you to
log in.

Fix:

```bash
lpass login <email>
```

### Python in this repo

Two “modes” are supported:

1. **Devenv** (recommended for contributors)
   - `devenv.nix` pins a Python (currently 3.13) plus `pytest` and `ruff`.
2. **Minimal environments**
   - Tests are written so they can run with the stdlib `unittest` when needed.

Minimal test run:

```bash
python -m unittest -q
```

If you have `pytest` installed, prefer the module form to avoid PATH/interpreter mismatches:

```bash
python -m pytest -q
```

## Scripts (CLI tools)

Scripts are installed by linking `scripts/<name>` into `~/.local/bin` via `./scripts/setup-links`.

### `rebuild`: safer NixOS rebuilds with mirror support

`rebuild` is a wrapper around `nixos-rebuild switch` that supports a safe, convenient flow built around a root-owned `/etc/nixos` checkout.

Default behavior (when not using `--dev`):

- Uses flake source: `/etc/nixos`
- Target host defaults to `/etc/hostname`
- Runs `nixos-rebuild switch --flake /etc/nixos/.#<hostname>`
- Syncs `/etc/nixos` from a **local bare mirror** (default: `/var/lib/nixos-setup/mirror.git`)

Key flags:

- `--dev`: use the current repo checkout as flake source (for development)
- `--flake PATH`: explicit flake directory override
- `--mirror` / `--no-mirror`: force-enable / disable mirror syncing
- `--mirror-dir PATH`: override mirror location
- `--offline-ok`: keep going if fetching updates fails

#### Why the mirror workflow exists

Using flakes, `/etc/nixos` must be a valid flake source tree. Many “symlink farm” setups fail because Nix evaluates the flake source as a Git tree and errors if it sees untracked symlinked paths.

This repo’s recommended approach:

1. Your **user** fetches from GitHub into a **local bare mirror** (uses your SSH keys)
2. Root updates `/etc/nixos` from that mirror (no GitHub creds / no network needed)

This preserves good security separation: root doesn’t need GitHub access.

#### One-time setup (NixOS configuration)

Host configuration should ensure the mirror directory exists and is writable by an appropriate group (commonly `nixos-setup`) and that sudo rules allow the minimal privileged operations needed by `rebuild`.

See the host config under `hosts/<hostname>/configuration.nix` for the exact setup.

#### Offline rebuilds

If you’re offline, the “fetch into mirror” step can fail. Use:

```bash
rebuild --offline-ok
```

This continues using whatever `/etc/nixos` already has checked out.

Important constraints:

- Offline rebuilds require that `/etc/nixos` has already been bootstrapped as a clone at least once.

### `sync-vscode-settings`: capture runtime preferences into Nix

This repo intentionally supports a **hybrid VS Code settings** workflow:

- Home Manager manages “structural” settings (tool paths, formatters, language servers)
- VS Code is allowed to modify “preference” settings at runtime (UI preferences, “don’t show again”, etc.)

To snapshot runtime-modified preferences into Nix (useful for sharing across machines):

- `./scripts/sync-vscode-settings`

What it does:

1. Reads `~/.config/Code/User/settings.json`
2. Filters out keys that are managed declaratively
3. Writes `home/features/vscode/user-settings.nix`

Deep dive:

- `docs/VSCODE-SETTINGS.md`

### `setup-links`: link repo config + scripts into standard locations

`./scripts/setup-links` creates symlinks from this repo to common user locations.

Highlights:

- Links scripts into `~/.local/bin`
- Can also link host-specific Home Manager entrypoints (from `hosts/<hostname>/`) into `~/.config/home-manager/`
- Refuses to modify **root-owned** targets (it will warn and print the command to run manually as root if you really want it)

### `import-dotfiles`: import existing user config into `dotfiles/`

This helps bootstrap the repo from an existing machine by copying:

- `~/.<NAME>` → `dotfiles/home/<NAME>`
- `~/.config/<NAME>` → `dotfiles/config/<NAME>`

Safety properties:

- Does **not** overwrite existing paths in `dotfiles/`

## VS Code (Home Manager feature)

The VS Code feature lives under `home/features/vscode/`.

It provides:

- A curated extension set, including Marketplace-sourced extensions when nixpkgs doesn’t package them
- A Home Manager activation script that ensures VS Code’s `settings.json` stays **writable**, while still keeping managed settings consistent

Key files:

- `home/features/vscode/default.nix`: extensions + “structural” settings
- `home/features/vscode/activation-vscode-settings.sh.tpl`: settings merge logic
- `home/features/vscode/user-settings.nix`: generated file (preferences snapshot)

More docs:

- `docs/VSCODE-SETTINGS.md`

## GitHub labels

Dependabot (and some workflows) expect certain labels (for example `dependencies` and
`github-actions`) to exist in the repository.

This repo keeps the label catalog in `/.github/labels.yml` and provides a small sync script
that uses the `gh` CLI.

Typical usage:

```bash
scripts/sync-github-labels --dry-run
scripts/sync-github-labels
```

Useful flags:

- `--repo OWNER/REPO` to target a specific repo (defaults to whatever `gh` detects).
- `--delete-unmanaged` to delete labels not listed in `labels.yml`.
- `docs/VSCODE-EXTENSIONS-MARKETPLACE.md`

## PATH troubleshooting

If scripts installed via `setup-links` aren’t found, usually `~/.local/bin` isn’t in `$PATH`.

Quick checks:

```bash
echo "$PATH" | grep -q "$HOME/.local/bin" && echo OK || echo MISSING
test -f "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh" && echo OK || echo MISSING
```

This repo’s Home Manager bash module sources `hm-session-vars.sh` for both login and interactive shells.

## Git defaults and signing

This setup configures Git via Home Manager. A few notable defaults:

- `git pull` uses **merge** by default when histories diverge (`pull.rebase = false`).

### Optional: SSH commit signing

If you enable SSH signing but Git can’t determine the signing key, you may see:

> `fatal: either user.signingkey or gpg.ssh.defaultKeyCommand needs to be configured`

The simplest approach is a dedicated signing key:

```bash
ssh-keygen -t ed25519 -C "git-signing" -f ~/.ssh/id_ed25519_git_signing
```

Then add the public key to GitHub as a **Signing key** and configure Home Manager (see `home/modules/git.nix`).

## Troubleshooting and safety notes

### “Could not find flake.nix in /etc/nixos”

`rebuild` defaults to `/etc/nixos` unless using `--dev`. Fix options:

- Bootstrap `/etc/nixos` using the mirror workflow (recommended)
- Or run `rebuild --dev` from your repo checkout
- Or point explicitly: `rebuild --flake /path/to/flake`

### “Refusing to overwrite existing git repo at /etc/nixos”

In mirror mode, `rebuild` refuses to overwrite an existing Git repo at `/etc/nixos`. Move it aside manually if you truly intend to replace it.

### Pre-commit failures due to missing tools

Prefer running pre-commit inside devenv:

- `devenv shell -- pre-commit run --all-files`

This ensures the same versions and PATH as CI.

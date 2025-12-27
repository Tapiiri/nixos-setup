# nixos-setup

## Repo scripts

Some helper scripts live under `scripts/`. They are designed to be runnable as normal executables (for example `rebuild`, including via `sudo`) and implemented in Python for testability.

### Available Scripts

- `rebuild` - NixOS rebuild wrapper with mirror support
- `import-dotfiles` - Import dotfiles from home directory
- `setup-links` - Create symlinks for scripts in `~/.local/bin`
- `devshell` - Enter the development shell environment
- `sync-vscode-settings` - Sync VS Code runtime settings back to Nix config (see [VS Code Settings Guide](docs/VSCODE-SETTINGS.md))

### Python version and dependencies

Python tooling for this repo is provided via Home Manager when `my.devtools.enable = true`.

- Python is pinned in `home/modules/devtools.nix` (currently `pkgs.python313`).
- Script/test dependencies (like `pytest`/`ruff` if used) should be added there via `py.pkgs`.

### Running tests

This repo’s unit tests use the Python standard library `unittest`, so they work in minimal environments.

Run:

- `python -m unittest -q`

If you prefer pytest locally, you can add it in `home/modules/devtools.nix` (already included) and run:

- `pytest -q`

If you run into `ModuleNotFoundError: No module named 'pytest'` even though `pytest` is on PATH, you're typically picking up a `pytest` launcher that points at a different Python than the one in your current shell session.

Most reliable options:

- Use the interpreter module form:
	- `python -m pytest -q`
- Or use the repo's dev-only flake shell (pins Python + pytest together without touching the NixOS flake outputs):
	- `nix develop ./dev -c pytest -q`

If you want an interactive shell (so you can just type `pytest` afterwards), enter it first and then run commands normally:

- `nix develop ./dev`
- then: `pytest -q`

There's also a convenience wrapper script:

- `./scripts/devshell`
- then: `pytest -q`

Optional: if you use `direnv`, you can add an `.envrc` that auto-enters the dev shell on `cd`.

## Pre-commit

Hooks auto-install when you enter the dev shell (if not already present) so `nix develop ./dev` is usually enough. To force a reinstall:

- `nix develop ./dev -c pre-commit install --install-hooks`

Run all checks locally (matches CI):

- `nix develop ./dev -c pre-commit run --all-files`

Included hooks: `nix flake check`, `nixpkgs-fmt`, `yamllint`, `actionlint` (workflows), `ruff check`, and `python -m pytest -q tests`.

VS Code: recommended extensions include the Nix environment selector plus Python/Ruff. With the Nix Env Selector extension installed, set the workspace Nix file to `dev/flake.nix` so VS Code terminals inherit the dev shell and pick up the pre-commit auto-install.

CI runs `pre-commit run --all-files` via the same dev shell to match local tooling.

### PATH troubleshooting (why `rebuild` isn't found)

Scripts from `scripts/` are linked into `~/.local/bin` by `scripts/setup-links.sh`.
For the commands to be found, `~/.local/bin` must be in your `$PATH`.

In this setup, `~/.local/bin` is exported via Home Manager session variables
(`home.sessionPath` / `hm-session-vars.sh`). If your PATH looked correct in one
session but changed after reboot, the most common cause is that your shell
isn't sourcing Home Manager's session vars.

Quick checks:

- `echo "$PATH" | grep -q "$HOME/.local/bin" && echo OK || echo MISSING`
- `test -f "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh" && echo OK || echo MISSING`

This repo's module `home/modules/shell-bash.nix` sources `hm-session-vars.sh`
for both login shells and interactive shells.

## Git defaults

This setup configures Git (via Home Manager) so `git pull` uses **merge** by
default when local/remote histories diverge:

- `pull.rebase = false`

### Commit signing (SSH)

By default, this repo configures Git without forcing signing. If you enable SSH
commit signing but Git cannot determine the signing key, you'll see:

- `fatal: either user.signingkey or gpg.ssh.defaultKeyCommand needs to be configured`

To use GitHub's **Verified** badge with SSH signing:

1. Create a dedicated signing key:
	- `ssh-keygen -t ed25519 -C "git-signing" -f ~/.ssh/id_ed25519_git_signing`
2. Add the **public** key to GitHub:
	- Settings → SSH and GPG keys → New SSH key → Key type: **Signing key**
3. Configure Home Manager to enable signing and point Git at the public key
	(see `home/modules/git.nix`):
	- enable `my.git.signing.enable = true;`
	- set `my.git.signing.key = "~/.ssh/id_ed25519_git_signing.pub";`

Alternative: instead of `user.signingKey`, you can configure
`gpg.ssh.defaultKeyCommand` to dynamically choose a key, but a fixed
`user.signingKey` is simplest.

You can still override per-invocation:

- `git pull --rebase`
- `git pull --no-rebase`
- `git pull --ff-only`

## /etc/nixos and flakes (recommended setup)

This repo uses flakes. The `rebuild` wrapper defaults to:

- `nixos-rebuild switch --flake /etc/nixos/.#<hostname>`

That means whatever is in `/etc/nixos` must be a *valid flake source tree*.

### Why symlinks can break

If `/etc/nixos` is itself a Git repository and you symlink in directories like
`home/` or `hosts/`, Git will see them as **untracked paths** in `/etc/nixos`.
Nix treats flake sources as Git trees and will error out with messages like:

- `Path 'home' in the repository "/etc/nixos" is not tracked by Git.`

### Recommended fix: local mirror + root-owned /etc/nixos clone

Instead of making `/etc/nixos` a separate git repo with symlinks (breaks flakes)
or a git worktree (can create permission/admin-dir pitfalls when mixing root and
user operations), this repo supports a **local mirror** workflow:

1. Your user fetches from GitHub into a local bare mirror (uses your SSH keys)
2. Root fast-forwards `/etc/nixos` from that *local* mirror (no GitHub creds)

By default the mirror lives at:

- `/var/lib/nixos-setup/mirror.git`

#### One-time setup (implemented via NixOS config)

In `hosts/<host>/configuration.nix`, we:

- create group `nixos-setup`
- add your user to that group
- create `/var/lib/nixos-setup` with group write + setgid
- add sudo rules so members of `nixos-setup` can run the minimal privileged
	commands used by `rebuild --mirror` (including `git` for `/etc/nixos` updates)

After switching to that config, the first run of `rebuild --mirror` will create
the bare mirror (if missing) and bootstrap `/etc/nixos` as a clone of the mirror.

#### Daily usage

Prefer running:

- `rebuild`

By default, when rebuilding from `/etc/nixos`, `rebuild` will sync `/etc/nixos`
via the local mirror.

You can still run mirror sync explicitly:

- `rebuild --mirror`

Optional flags:

- `--mirror-dir <path>`: override mirror location
- `--offline-ok`: proceed if fetching from GitHub fails (uses last fetched mirror)
- `--no-mirror`: disable mirror sync even when rebuilding from `/etc/nixos`

#### Dev mode (`--dev`) and offline workflow

The `--dev` flag is intended for working on this repo directly (your dev checkout)
while still using the mirror + `/etc/nixos` clone setup.

When you combine `--dev` with `--offline-ok`, you get an extra offline-friendly
fallback:

- `rebuild --dev --offline-ok` will still *try* to fetch into the mirror first.
- If that fetch fails (e.g. you're offline), it will push your local dev repo's
	current `main` into the local mirror, and then update `/etc/nixos` from that.

This lets you iterate locally and still rebuild against `/etc/nixos` even when
you have no network, as long as your local dev checkout has the commits you want.

#### Offline rebuilds

The mirror workflow is designed so that **root never needs network access**.
However, if you're fully offline, the *user-side* fetch into the mirror will
fail.

To rebuild while offline, run:

```bash
rebuild --offline-ok
```

Behavior:

- `rebuild` will attempt to update the bare mirror (`/var/lib/nixos-setup/mirror.git`).
- If fetching fails and `--offline-ok` was provided, it continues.
- It then uses whatever is already in `/etc/nixos` (the last successfully
	synced state) to do `nixos-rebuild`.

Important notes:

- Offline rebuilds will only work if you have **already bootstrapped** `/etc/nixos`
	at least once (so it exists as a git clone), and you have fetched at least
	once previously.
- To prepare for offline use, do a normal online sync first (e.g. run `rebuild`
	once while connected).
- If `/etc/nixos` is missing or not a valid git clone, the initial bootstrap
	requires access to the mirror and typically one online run.

### Running rebuild (no sudo)

Prefer running `rebuild` as your normal user. The script will do the sync step
as your user (for GitHub access) and invoke `sudo nixos-rebuild ...` internally
for the privileged part.

### Cleaning up an old git-worktree-based setup

If you previously tried to manage `/etc/nixos` as a git worktree of your dev
checkout, you may have leftover worktree metadata under your repo (often owned
by root), which can cause permission errors even after switching to mirror mode.

From your **dev checkout** (this repo), you can clean it up like this:

```bash
# Show registered worktrees
git worktree list

# If /etc/nixos is still registered as a worktree, remove it from the repo's
# worktree registry (this does NOT delete /etc/nixos contents by itself).
git worktree remove --force /etc/nixos

# Prune stale worktree entries
git worktree prune
```

If you still have permission problems because `.git/worktrees/*` is owned by
root from earlier experiments:

```bash
# Inspect ownership
ls -la .git/worktrees || true

# If needed, remove the stale worktree admin dirs (be careful; this affects worktree tracking)
sudo rm -rf .git/worktrees
```

After that, `rebuild --mirror` should not rely on worktrees and the permission
mismatch problems should stop.

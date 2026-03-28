# Repository Layout

How the repo is organized and why.

## Top-level structure

| Path | Purpose |
|------|---------|
| `flake.nix` / `flake.lock` | Flake entrypoint + pinned inputs |
| `hosts/<hostname>/` | Per-host NixOS configuration |
| `home/modules/` | Reusable Home Manager modules |
| `home/features/` | Higher-level feature bundles (e.g. VS Code) |
| `home/overlays/` | Nixpkgs overlays |
| `modules/` | System-level NixOS modules (e.g. `rebuild.nix`, `tailscale.nix`) |
| `scripts/` | User-facing CLI wrappers |
| `scripts_py/` | Python implementations (testable, imported by wrappers) |
| `tests/` | Unit tests for scripts |
| `docs/` | Documentation source (MkDocs site + deep-dives) |
| `dotfiles/` | Raw dotfiles managed by symlink |
| `schemas/` | SchemaStore index and vendored schemas |
| `projects/` | Standalone sub-projects (e.g. ESP32-IR) |

## Flake outputs

The flake exposes `nixosConfigurations.<hostname>` as its primary output.
Host configs are addressed with:

```bash
nixos-rebuild switch --flake /etc/nixos/.#<hostname>
```

!!! tip "Discovering outputs"
    To see what the flake exposes:
    ```bash
    nix flake show --all-systems
    ```
    To force evaluation of Home Manager modules (e.g. to surface a hash mismatch):
    ```bash
    nix build .#nixosConfigurations.<host>.config.system.build.toplevel
    ```

### Host naming

Host configs live under `hosts/<hostname>/` and must match the machine hostname.
Each host directory typically contains:

- `configuration.nix` — NixOS system configuration
- `hardware-configuration.nix` — auto-generated hardware config
- `home.nix` — optional host-specific Home Manager entrypoint

## Home Manager organization

### Modules (`home/modules/`)

Reusable, focused modules that each manage one concern:

| Module | What it manages |
|--------|----------------|
| `core.nix` | Base packages and session variables |
| `shell-bash.nix` | Bash configuration |
| `git.nix` | Git config, aliases, signing |
| `devtools.nix` | Development tools and language servers |
| `browsers.nix` | Browser packages |
| `gh.nix` | GitHub CLI configuration |
| `onepassword.nix` | 1Password integration |
| `tailscale.nix` | Tailscale VPN |
| `telegram.nix` | Telegram desktop |

Modules are enabled via host configs — not all modules are active on every host.

### Features (`home/features/`)

Feature bundles group related modules, config files, and activation scripts.
They're more complex than individual modules:

- **`home/features/vscode/`** — VS Code with hybrid settings management,
  curated extensions, and activation scripts. See the
  [VS Code Settings](reference/vscode-settings.md) reference for the full workflow.

## Dotfiles strategy

This repo follows **Model A**: Home Manager / Nix is the source of truth for
most configuration. The `dotfiles/` directory handles a small set of explicit
"raw" files that are symlinked into place.

### Layout

- `dotfiles/home/*` → `$HOME/.*`
    - Example: `dotfiles/home/bashrc` → `~/.bashrc`
- `dotfiles/config/*` → `~/.config/*` (if applicable)

### Sync direction

Symlinks are **repo → system**: when you edit `~/.bashrc` (once it's a symlink),
you're editing the file inside the repo.

### Managing dotfiles

```bash
# Link dotfiles (part of setup-links)
./scripts/setup-links

# Import existing dotfiles into the repo
./scripts/import-dotfiles
```

`import-dotfiles` copies `~/.<name>` → `dotfiles/home/<name>` and will not
overwrite files that already exist in the repo.

## Scripts design

Scripts follow a **thin wrapper + testable implementation** pattern:

- `scripts/<name>` — executable wrapper (bootstraps `sys.path`, delegates to Python)
- `scripts_py/cli/<name>.py` — actual implementation

See the [Scripts Overview](scripts.md) for the full inventory and details.

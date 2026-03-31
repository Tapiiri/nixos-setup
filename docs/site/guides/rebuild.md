# Rebuild & System Updates

The `rebuild` command is the primary entrypoint for applying NixOS configuration
changes. It wraps `nixos-rebuild switch` with a **mirror-based workflow** that
keeps root/user privilege separation clean.

If you are using this repo on a non-NixOS Linux system such as Ubuntu on WSL,
use `hm-switch` instead. `rebuild` is intentionally NixOS-only because it
assumes `/etc/nixos`, root-owned system state, and `nixos-rebuild`.

## How it works

`rebuild` is actually **two programs**:

| Command | Role |
|---------|------|
| `rebuild` | **Dispatcher** — chooses remote vs local, supports `--dev` |
| `rebuild-inner` | **Implementation** — runs `nixos-rebuild switch` with mirror support |

When you run `rebuild` without flags:

1. The dispatcher fetches the **remote flake** from GitHub (`github:Tapiiri/nixos-setup#rebuild-inner`)
2. The implementation syncs `/etc/nixos` from a local bare mirror
3. `nixos-rebuild switch --flake /etc/nixos/.#<hostname>` runs

```text
rebuild (dispatcher)
  ├─ online?  → nix run github:Tapiiri/nixos-setup#rebuild-inner
  └─ offline? → refuse (unless --offline-ok)
                  └─ run local rebuild-inner against /etc/nixos
```

## The mirror workflow

### Why it exists

Using flakes, `/etc/nixos` must be a valid flake source tree. Many
"symlink-farm" setups fail because Nix evaluates the flake source as a Git
tree and errors when it finds untracked symlinked paths.

This repo's approach:

1. Your **user account** fetches from GitHub into a **local bare mirror** (uses your SSH keys)
2. **Root** updates `/etc/nixos` from that mirror (no GitHub creds, no network)

```text
GitHub ──(user fetch)──▶ /var/lib/nixos-setup/mirror.git
                              │
                        (root fast-forward)
                              │
                              ▼
                         /etc/nixos  ◀── nixos-rebuild reads this
```

This preserves good security separation — root never needs GitHub access.

### One-time setup

Your host NixOS configuration needs to:

- Create the mirror directory (default: `/var/lib/nixos-setup/mirror.git`)
- Make it writable by the appropriate group (commonly `nixos-setup`)
- Set up sudo rules for the minimal privileged operations `rebuild` needs

See your host config under `hosts/<hostname>/configuration.nix` for the exact setup,
and `modules/rebuild.nix` for the NixOS module that manages this.

## Flags reference

| Flag | Description |
|------|-------------|
| `--dev` | Use current repo checkout as flake source (for development) |
| `--flake PATH` | Explicit flake directory override |
| `--mirror` / `--no-mirror` | Force-enable / disable mirror syncing |
| `--mirror-dir PATH` | Override mirror location |
| `--upstream-url URL` | Git URL for creating the bare mirror when it doesn't exist |
| `--ref REF` | Git ref to fast-forward `/etc/nixos` to (default: `origin/main`) |
| `--offline-ok` | Keep going if fetching updates fails |
| `--bootstrap-permissions` | Create/fix mirror parent dir permissions using sudo |

## Standalone Home Manager on Ubuntu/WSL

For non-NixOS setups, this flake also exposes standalone Home Manager profiles.
The matching helper is `hm-switch`, which runs `home-manager switch` against a
profile in this repo instead of invoking `nixos-rebuild`.

Current standalone profiles:

| Profile | Intended use |
|---------|--------------|
| `tapiiri` | Personal standalone Linux / WSL home environment |
| `tapiiri-wsl` | Minimal WSL profile with only Claude Code |
| `ilmari` | Work standalone Linux / WSL home environment |

Examples:

```bash
# Run directly from the checkout
nix run .#hm-switch -- tapiiri

# Or use a remote flake without cloning first
nix run github:Tapiiri/nixos-setup#hm-switch -- tapiiri

# After installing the package/profile, omit the profile if
# NIXOS_SETUP_HM_PROFILE is set in your shell session
hm-switch
```

`hm-switch` defaults to the `NIXOS_SETUP_HM_PROFILE` environment variable, then
falls back to the current Unix username.

For a step-by-step Ubuntu setup flow, see [Ubuntu WSL Setup](wsl.md).

## Defaults precedence

Settings are resolved in this order (first match wins):

1. **CLI flags** — e.g. `--upstream-url`, `--mirror-dir`, `--ref`
2. **Environment variables** — `NIXOS_SETUP_REBUILD_UPSTREAM_URL`, `NIXOS_SETUP_REBUILD_MIRROR_DIR`, `NIXOS_SETUP_REBUILD_REF`, `NIXOS_SETUP_REBUILD_OFFLINE_OK`
3. **Config file** — `/etc/nixos-setup/rebuild.conf` (INI format, `[rebuild]` section)

## Common scenarios

### "I just want to rebuild"

```bash
rebuild
```

This fetches the latest from GitHub and applies it. The most common daily workflow.

### "I'm developing locally"

```bash
rebuild --dev
```

Uses your current repo checkout as the flake source — no mirror, no fetch.
The dispatcher runs the **local** `rebuild-inner` directly.

### "I'm offline"

```bash
rebuild --offline-ok
```

Allows the rebuild to proceed using whatever is currently in `/etc/nixos`.
Requires that `/etc/nixos` has already been bootstrapped as a clone at least once.

!!! warning
    Offline rebuilds use whatever state `/etc/nixos` was last synced to.
    You won't get any upstream changes until you're back online.

### Running without `setup-links`

If you haven't linked the scripts, you can still run rebuild via `nix run`:

```bash
# Dispatcher
nix run github:Tapiiri/nixos-setup#rebuild -- --help

# Implementation directly
nix run github:Tapiiri/nixos-setup#rebuild-inner -- --help
```

!!! tip
    Note the `--` separator — without it, flags go to `nix run` instead of the script.
    When running the linked executable directly (`rebuild --help`), you don't need `--`.

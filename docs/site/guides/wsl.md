# Ubuntu WSL Setup

This guide covers the minimal standalone Home Manager setup for Ubuntu on WSL.
The intended profile is `tapiiri-wsl`.

## What this installs

Today the `tapiiri-wsl` profile is intentionally narrow. It installs:

- `claude-code`
- `hm-switch`

It does **not** attempt to behave like the full NixOS profile.

## Prerequisites

Inside your Ubuntu WSL instance, make sure you have:

- a working Nix installation with flakes enabled
- `git`
- access to this repository, either by cloning it or by using the GitHub flake directly

If Nix is not installed yet, install it first using your preferred Linux Nix installer.

## Option 1: Install from a local checkout

Clone the repository in WSL:

```bash
git clone git@github.com:Tapiiri/nixos-setup.git
cd nixos-setup
```

Activate the WSL profile:

```bash
nix run .#hm-switch -- tapiiri-wsl
```

This performs the first `home-manager switch` without requiring a preinstalled
`home-manager` command.

After the first activation, reload your shell and you can use:

```bash
hm-switch
```

The profile sets `NIXOS_SETUP_HM_PROFILE=tapiiri-wsl`, so the profile name does
not need to be repeated on later updates.

## Option 2: Install directly from GitHub

If you do not want to clone the repo first, you can activate it straight from GitHub:

```bash
nix run github:Tapiiri/nixos-setup#hm-switch -- tapiiri-wsl
```

This is useful for first-time bootstrap on a fresh WSL instance.

## Updating later

If you installed from a local checkout:

```bash
cd ~/nixos-setup
git pull --ff-only
hm-switch
```

If you prefer to update straight from GitHub each time:

```bash
nix run github:Tapiiri/nixos-setup#hm-switch -- tapiiri-wsl
```

## Notes

- `rebuild` is for NixOS only. On Ubuntu WSL, use `hm-switch`.
- Flakes only see files tracked by Git. If you add new Home Manager modules or
  profile files locally, stage or commit them before expecting `nix run` or
  `nix build` to see them.
- This profile is intentionally minimal for now; add more packages and modules only
  when the WSL workflow is clear.
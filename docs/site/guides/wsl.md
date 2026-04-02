# Ubuntu WSL Setup

This guide covers the minimal standalone Home Manager setup for Ubuntu on WSL.
The intended profile is `tapiiri-wsl`.

## What this installs

Today the `tapiiri-wsl` profile is intentionally narrow. It installs:

- `claude-code`
- `hm-switch`
- `tailscale`
- `setup-wsl-ssh`

It does **not** attempt to behave like the full NixOS profile.

## Prerequisites

Inside your Ubuntu WSL instance, make sure you have:

- a working Nix installation with flakes enabled
- `git`
- access to this repository, either by cloning it or by using the GitHub flake directly

If Nix is not installed yet, install it first using your preferred Linux Nix installer.

If `nix run` complains that `nix-command` or `flakes` is disabled, either:

1. use the one-shot form with global Nix flags before the subcommand, or
2. enable the features permanently in your Nix config.

One-shot form:

```bash
nix --extra-experimental-features 'nix-command flakes' run github:Tapiiri/nixos-setup#hm-switch -- tapiiri-wsl
```

Persistent config for single-user installs:

```bash
mkdir -p ~/.config/nix
printf 'experimental-features = nix-command flakes\n' >> ~/.config/nix/nix.conf
```

After that, plain `nix run` works as shown below.

## Dokploy deploy-node access over Tailscale

If this WSL instance should act as a Dokploy deploy node, the repo now ships a
helper that configures a normal OpenSSH server for the Home Manager user.

After activating `tapiiri-wsl`, run:

```bash
sudo setup-wsl-ssh --allow-root-login
```

What it does:

- installs `openssh-server` with `apt-get` if it is missing
- writes an SSH drop-in that disables password login and, with `--allow-root-login`, permits key-only root login for Dokploy
- enables and restarts the `ssh` service
- if `ufw` is installed and active, opens TCP port 22 only on `tailscale0`

What it does not do:

- it does not install the Tailscale system daemon for Ubuntu; keep using your existing Tailscale install
- it does not add Dokploy's SSH key for you

Before Dokploy can connect, add Dokploy's public key to `~/.ssh/authorized_keys`
for the target user. If you use `--allow-root-login`, also add the same key to
`/root/.ssh/authorized_keys` and point Dokploy at `root@<tailscale-ip>:22`.

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

If your Nix install does not yet have flakes enabled, use:

```bash
nix --extra-experimental-features 'nix-command flakes' run .#hm-switch -- tapiiri-wsl
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

If your Nix install does not yet have flakes enabled, use:

```bash
nix --extra-experimental-features 'nix-command flakes' run github:Tapiiri/nixos-setup#hm-switch -- tapiiri-wsl
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

Or, without persistent Nix config:

```bash
nix --extra-experimental-features 'nix-command flakes' run github:Tapiiri/nixos-setup#hm-switch -- tapiiri-wsl
```

## Notes

- `rebuild` is for NixOS only. On Ubuntu WSL, use `hm-switch`.
- `--extra-experimental-features` is a global `nix` option, so it must appear before `run`.
- Flakes only see files tracked by Git. If you add new Home Manager modules or
  profile files locally, stage or commit them before expecting `nix run` or
  `nix build` to see them.
- This profile is intentionally minimal for now; add more packages and modules only
  when the WSL workflow is clear.
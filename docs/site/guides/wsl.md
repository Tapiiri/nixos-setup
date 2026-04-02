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

No local clone of this repository is required. The bootstrap command fetches
everything from GitHub.

If Nix is not installed yet, install it first using your preferred Linux Nix
installer.

### Enabling flakes

If `nix run` complains that `nix-command` or `flakes` is disabled, enable them
permanently before proceeding:

```bash
mkdir -p ~/.config/nix
printf 'experimental-features = nix-command flakes\n' >> ~/.config/nix/nix.conf
```

Alternatively, prefix every `nix` invocation with the global flag (must appear
**before** the subcommand):

```bash
nix --extra-experimental-features 'nix-command flakes' run ...
```

## Bootstrap

Run a single command to activate the `tapiiri-wsl` profile:

```bash
nix run github:Tapiiri/nixos-setup#hm-switch -- tapiiri-wsl
```

This fetches the flake from GitHub, evaluates the Home Manager profile, and
activates it. No local checkout is needed.

After the first activation, reload your shell (or open a new terminal). The
profile installs `hm-switch` onto your PATH and sets the environment variable
`NIXOS_SETUP_HM_PROFILE=tapiiri-wsl`, so subsequent updates are just:

```bash
hm-switch
```

The installed `hm-switch` always evaluates the flake from GitHub, so you
automatically get the latest committed configuration.

## Updating

```bash
hm-switch
```

That's it. The command fetches the latest flake from GitHub and runs
`home-manager switch`. No `git pull` or local repo required.

## Dokploy deploy-node access over Tailscale

If this WSL instance should act as a Dokploy deploy node, the repo ships a
helper that configures a normal OpenSSH server for the Home Manager user.

After activating `tapiiri-wsl`, run:

```bash
sudo setup-wsl-ssh --allow-root-login
```

What it does:

- installs `openssh-server` with `apt-get` if it is missing
- writes an SSH drop-in that disables password login and, with
  `--allow-root-login`, permits key-only root login for Dokploy
- enables and restarts the `ssh` service
- if `ufw` is installed and active, opens TCP port 22 only on `tailscale0`

What it does not do:

- it does not install the Tailscale system daemon for Ubuntu; keep using your
  existing Tailscale install
- it does not add Dokploy's SSH key for you

Before Dokploy can connect, add Dokploy's public key to
`~/.ssh/authorized_keys` for the target user. If you use `--allow-root-login`,
also add the same key to `/root/.ssh/authorized_keys` and point Dokploy at
`root@<tailscale-ip>:22`.

## Advanced: local checkout

For development or testing local changes, you can clone the repo and point
`hm-switch` at it:

```bash
git clone git@github.com:Tapiiri/nixos-setup.git
cd nixos-setup
nix run .#hm-switch -- tapiiri-wsl
```

Or, if `hm-switch` is already installed:

```bash
hm-switch --flake ~/nixos-setup tapiiri-wsl
```

## Notes

- `rebuild` is for NixOS only. On Ubuntu WSL, use `hm-switch`.
- `--extra-experimental-features` is a global `nix` option, so it must appear
  before `run`.
- This profile is intentionally minimal for now; add more packages and modules
  only when the WSL workflow is clear.
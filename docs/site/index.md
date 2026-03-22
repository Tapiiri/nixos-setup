# nixos-setup

NixOS + Home Manager flake repository with tested helper CLIs, reproducible
dev tooling, and automated CI attestation.

## What this repo provides

- **NixOS system configuration** via a flake (`flake.nix`) with per-host configs
  under `hosts/`.
- **Home Manager modules** for user-level programs, shell, dotfiles, and VS Code.
- **Tested utility scripts** — thin shell wrappers in `scripts/` backed by Python
  implementations in `scripts_py/`, all covered by `pytest` unit tests.
- **Reproducible dev environment** powered by [devenv.sh](https://devenv.sh) with
  pinned linters, formatters, and tasks.

## Quick links

| Topic | Page |
|-------|------|
| First-time setup | [Quickstart](quickstart.md) |
| Repo layout & design decisions | [Architecture](architecture.md) |
| Script inventory | [Scripts](scripts.md) |
| Dev shell, tasks, CI | [Dev Environment](dev-environment.md) |
| Common issues | [Troubleshooting](troubleshooting.md) |

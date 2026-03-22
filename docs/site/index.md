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
- **Mirror-based rebuild workflow** — root never needs GitHub access.
- **CI attestation** — skip redundant CI runs by attesting locally.

## Quick links

| Topic | Page |
|-------|------|
| First-time setup | [Quickstart](quickstart.md) |
| Repo layout & design decisions | [Architecture](architecture.md) |
| Script inventory & design | [Scripts](scripts.md) |
| Rebuild & mirror workflow | [Rebuild guide](guides/rebuild.md) |
| Secrets & password managers | [Secrets guide](guides/secrets.md) |
| Local CI attestation | [CI & Attestation guide](guides/ci-attestation.md) |
| Dev shell, tasks, CI | [Dev Environment](dev-environment.md) |
| Git config & GitHub tooling | [Git & GitHub](git-github.md) |
| Common issues | [Troubleshooting](troubleshooting.md) |
| VS Code settings merge workflow | [VS Code Settings](reference/vscode-settings.md) |
| Marketplace extension packaging | [VS Code Extensions](reference/vscode-extensions.md) |

## Who is this for?

These docs serve as both **personal reference** ("how do I do X again?") and
**onboarding material** for anyone forking or contributing to this repo.


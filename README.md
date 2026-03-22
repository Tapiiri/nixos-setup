# nixos-setup

A personal NixOS + Home Manager flake repo, plus a small set of **tested helper CLIs** that make daily workflows predictable:

- **Mirror-based `/etc/nixos` flow** (root doesn't need network access)
- **Devenv-pinned dev tooling** (CI + pre-commit use the same tasks)
- **Hybrid VS Code settings**: declarative "structural" settings + runtime-mutable preferences
- **Repo utilities** in `scripts/` with Python implementations in `scripts_py/` and unit tests in `tests/`

📖 **Full documentation:** <https://Tapiiri.github.io/nixos-setup/>

## Quickstart

```bash
# 1. Link repo scripts into ~/.local/bin
./scripts/setup-links

# 2. Rebuild your system
rebuild
```

See the [Quickstart guide](https://Tapiiri.github.io/nixos-setup/quickstart/) for prerequisites, alternatives, and next steps.

## Documentation

| Topic | Link |
| ----- | ---- |
| First-time setup | [Quickstart](https://Tapiiri.github.io/nixos-setup/quickstart/) |
| Repo layout & design | [Architecture](https://Tapiiri.github.io/nixos-setup/architecture/) |
| Script inventory | [Scripts](https://Tapiiri.github.io/nixos-setup/scripts/) |
| Rebuild & mirror workflow | [Rebuild guide](https://Tapiiri.github.io/nixos-setup/guides/rebuild/) |
| Secrets & password managers | [Secrets guide](https://Tapiiri.github.io/nixos-setup/guides/secrets/) |
| CI attestation system | [CI & Attestation](https://Tapiiri.github.io/nixos-setup/guides/ci-attestation/) |
| Dev shell, tasks, CI | [Dev Environment](https://Tapiiri.github.io/nixos-setup/dev-environment/) |
| Git config & GitHub tools | [Git & GitHub](https://Tapiiri.github.io/nixos-setup/git-github/) |
| VS Code settings workflow | [VS Code Settings](https://Tapiiri.github.io/nixos-setup/reference/vscode-settings/) |
| Marketplace extensions | [VS Code Extensions](https://Tapiiri.github.io/nixos-setup/reference/vscode-extensions/) |
| Common issues | [Troubleshooting](https://Tapiiri.github.io/nixos-setup/troubleshooting/) |

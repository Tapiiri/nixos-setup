# Quickstart

Get from zero to a working NixOS rebuild in two steps.

## Prerequisites

- NixOS installed on your machine
- This repo cloned (typically to `/etc/nixos` for production, or anywhere for development)
- `git` available

## 1. Get the repo scripts on PATH

This repo ships user-facing executables under `scripts/`. Link them into
`~/.local/bin` so they're available everywhere:

```bash
./scripts/setup-links
```

!!! tip
    The linker is conservative — it only links **user-owned** targets.
    Root-owned targets are skipped with a warning showing the manual command
    if you really need it.

If `rebuild` or other scripts "aren't found" after this, see
[PATH troubleshooting](troubleshooting.md#path-issues).

## 2. Run the main workflows

### Rebuild your system

The recommended daily entrypoint:

```bash
rebuild
```

This fetches the latest configuration from GitHub and applies it via
`nixos-rebuild switch`. For details on what happens under the hood, see the
[Rebuild guide](guides/rebuild.md).

### Sync VS Code settings (optional)

If you use the hybrid VS Code settings workflow and want to capture runtime
preferences back into Nix:

```bash
sync-vscode-settings
```

See [VS Code Settings](reference/vscode-settings.md) for the full workflow.

## Alternative: no local linking required

You can run everything via `nix run` without installing anything:

=== "From GitHub (recommended)"

    ```bash
    # Dispatcher
    nix run github:Tapiiri/nixos-setup#rebuild -- --help

    # Implementation directly
    nix run github:Tapiiri/nixos-setup#rebuild-inner -- --help
    ```

=== "From local checkout"

    ```bash
    nix run .#rebuild -- --help
    nix run .#rebuild-inner -- --help
    ```

!!! note
    `nix run ... -- ...` needs the extra `--` so arguments reach the script.
    When running the linked executable directly (`rebuild --help`), you don't need it.

## Next steps

- [Repository layout](architecture.md) — understand how the repo is organized
- [Dev Environment](dev-environment.md) — set up the dev shell for contributing
- [Rebuild guide](guides/rebuild.md) — understand the mirror workflow and all flags

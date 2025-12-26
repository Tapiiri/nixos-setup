# VS Code (Home Manager feature)

This feature keeps VS Code configuration **co-located** under `home/features/vscode/`.

## Files

- `default.nix`
  - The Home Manager module entrypoint.
  - Defines `my.vscode.enable`.
  - Applies **managed/structural** settings (formatter + Nix tooling) and installs extensions.
  - Uses an activation script to ensure structural settings are present in:
    - `~/.config/Code/User/settings.json`

- `activation-vscode-settings.sh.tpl`
  - Bash template used by home-manager activation.
  - Rendered by Nix (substitution) so `default.nix` doesn’t embed the script.
  - Copies a generated JSON template into `settings.json` on first init and enforces
    managed keys via `jq` merge on subsequent activations (when available).

- `user-settings.nix`
  - **Generated** file containing user-specific settings that VS Code may change at runtime.
  - This is intentionally kept separate from structural settings.

## Syncing user settings back into Nix

Run:

```bash
./scripts/sync-vscode-settings
```

This writes/updates:

- `home/features/vscode/user-settings.nix`

Structural settings remain in `default.nix` and are not synced back.

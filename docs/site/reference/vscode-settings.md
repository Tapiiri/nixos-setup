# Hybrid VS Code Settings Management

This setup allows **both** Home Manager and VS Code to manage settings through
a merge-based workflow. Home Manager controls "structural" settings (tool paths,
formatters), while VS Code freely modifies "preference" settings at runtime.

## The problem

By default, Home Manager creates VS Code's `settings.json` as a **read-only
symlink** to the Nix store. This prevents VS Code from making any runtime
changes:

- "Don't show again" dialogs can't persist
- VS Code can't save UI preferences
- Any runtime configuration changes are lost

## The solution

A **Home Manager activation script** that:

1. Creates a **writable** `settings.json` file (not a symlink)
2. Initializes it with base settings on first run
3. On subsequent rebuilds, **merges** structural settings with existing user settings via `jq`
4. VS Code can freely modify the file between rebuilds

## How it works

### First rebuild

```text
home-manager activation script runs
  ↓
Removes old symlink (if exists)
  ↓
Creates writable settings.json with base settings
  ↓
VS Code can now modify the file freely
```

### Subsequent rebuilds

```text
home-manager activation script runs
  ↓
Detects existing writable settings.json
  ↓
Uses jq to merge:
  - Preserves all user settings
  - Overwrites managed structural settings (paths, LSP config)
  ↓
Result: Your preferences + Updated structural settings
```

### During daily use

```text
VS Code makes changes → Writes to settings.json → Changes persist!
```

## Settings categories

**Structural settings** (managed by Nix):

- Paths to formatters, language servers (e.g. `nix.serverPath`)
- Tool configurations that reference Nix store paths
- Core development workflow settings

**User preferences** (can be modified by VS Code):

- UI theme and appearance
- Window state and zoom levels
- "Don't show again" dialogs
- Telemetry and update settings
- Extension-specific preferences

### The full workflow

```text
┌──────────────────────────────────────────────────────────┐
│ 1. Initial Rebuild                                       │
│    Activation script creates writable settings.json      │
│    Initializes with structural settings from default.nix │
└──────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────┐
│ 2. Daily Usage                                           │
│    VS Code freely modifies settings.json                 │
│    Changes persist (UI preferences, dialogs, etc.)       │
└──────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────┐
│ 3. Subsequent Rebuilds                                   │
│    Activation script runs again                          │
│    Merges: User settings + Updated structural settings   │
│    Your preferences preserved, paths updated             │
└──────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────┐
│ 4. Optional: Sync to Nix (for multi-machine setup)      │
│    Run: ./scripts/sync-vscode-settings                   │
│    Captures user settings in user-settings.nix           │
│    Commit to share preferences across machines           │
└──────────────────────────────────────────────────────────┘
```

## Usage

### Daily use

**Just use VS Code normally.** Your changes persist automatically:

- Click "Don't show again" on dialogs
- Change UI preferences
- Adjust editor settings
- Configure extensions

All changes are saved to `~/.config/Code/User/settings.json` and persist across
VS Code restarts **and** Home Manager rebuilds.

### After rebuilding

Your user preferences are automatically preserved. The activation script only
updates the structural settings (paths to Nix store binaries).

### Syncing settings to Nix (multi-machine)

To share your VS Code preferences across multiple machines, capture them in Nix:

```bash
./scripts/sync-vscode-settings
```

This will:

1. Read your current VS Code settings from `~/.config/Code/User/settings.json`
2. Filter out the structural settings managed by Home Manager
3. Generate `home/features/vscode/user-settings.nix` with your user preferences
4. The file is automatically imported by `home/features/vscode/default.nix`

Then review and commit:

```bash
git diff home/features/vscode/user-settings.nix
git add home/features/vscode/user-settings.nix
git commit -m "Update VS Code user preferences"
```

!!! note
    The sync script is **optional**. It's only needed if you want to share
    preferences across machines or keep a declarative record. For single-machine
    use, VS Code manages everything automatically.

## Configuration

The setup in `home/features/vscode/default.nix`:

```nix
# Structural settings (always managed by Home Manager)
vscodeNixSettings = {
  "editor.formatOnSave" = true;
  "[nix]" = {
    "editor.defaultFormatter" = "jnoortheen.nix-ide";
  };
  "nix.enableLanguageServer" = true;
  "nix.serverPath" = nilBin;       # Points to Nix store
  "nix.formatterPath" = alejandraBin;  # Points to Nix store
  # ...
};

# User settings (synced from VS Code)
vscodeUserSettings =
  if builtins.pathExists ./user-settings.nix
  then (import ./user-settings.nix).userSettings
  else {};

# Both are merged together
allVscodeSettings = vscodeNixSettings // vscodeUserSettings;
```

### Adding structural settings

Edit `home/features/vscode/default.nix` and add to `vscodeNixSettings`:

```nix
vscodeNixSettings = {
  # ... existing settings ...

  # Add your own structural settings
  "python.defaultInterpreterPath" = "${pkgs.python3}/bin/python";
  "rust-analyzer.server.path" = "${pkgs.rust-analyzer}/bin/rust-analyzer";
};
```

!!! warning "Don't forget the filter list"
    Also add these keys to `get_managed_keys()` in
    `scripts_py/cli/sync_vscode_settings.py` so they're filtered out during sync:

    ```python
    def get_managed_keys() -> set[str]:
        return {
            "editor.formatOnSave",
            "[nix]",
            "nix.enableLanguageServer",
            # ... existing keys ...
            "python.defaultInterpreterPath",   # Add here
            "rust-analyzer.server.path",
        }
    ```

## Key files

| File | Role |
|------|------|
| `home/features/vscode/default.nix` | HM module: extensions + structural settings |
| `home/features/vscode/activation-vscode-settings.sh.tpl` | Bash template for the merge activation script |
| `home/features/vscode/user-settings.nix` | Generated: user-specific runtime settings |

## Implementation details

The key innovation is using a **Home Manager activation script** instead of
`programs.vscode.userSettings`:

```nix
# Instead of this (creates read-only symlink):
programs.vscode.userSettings = { ... };

# We use this (creates writable file with smart merging):
home.activation.vscodeSettings = lib.hm.dag.entryAfter ["writeBoundary"] ''
  # Creates/updates writable settings.json
  # Merges user settings + structural settings
'';
```

### What gets filtered during sync

The sync script filters out settings that:

1. Reference Nix store paths (these change across rebuilds)
2. Are explicitly listed in `get_managed_keys()`
3. Should always be managed declaratively

### Multi-machine setup

The generated `user-settings.nix` is machine-agnostic:

- Sync settings on your main machine
- Commit to git
- Other machines get the same user preferences
- Each machine can still make local changes (sync them later)

## Troubleshooting

### Settings.json is still a symlink

If after rebuilding, `~/.config/Code/User/settings.json` is still a symlink:

```bash
ls -la ~/.config/Code/User/settings.json
```

Fix:

1. Remove the symlink: `rm ~/.config/Code/User/settings.json`
2. Rebuild: `rebuild`
3. The activation script will create a writable file

### VS Code says settings are read-only

Check file permissions:

```bash
ls -la ~/.config/Code/User/settings.json
```

Should show `-rw-r--r--` (regular file). If it shows `lrwxrwxrwx` (symlink),
see above.

### Settings disappear after rebuild

This shouldn't happen — the activation script specifically preserves existing
settings. If it does:

1. Check the activation script output during rebuild
2. Verify `jq` is available: `which jq`
3. Check settings before and after rebuild

### Structural settings not updating

If paths to formatters/LSP servers are stale after a Nix store update, rebuild
again. The activation script will overlay fresh structural settings.

!!! tip "Non-default settings path"
    The default path is `~/.config/Code/User/settings.json`. If VS Code uses a
    different location, update `get_vscode_settings_path()` in
    `scripts_py/cli/sync_vscode_settings.py`.

## Extensions

If you need to package a Marketplace extension that isn't in nixpkgs, see the
[VS Code Extensions](vscode-extensions.md) reference.

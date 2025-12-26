# Hybrid VS Code Settings Management with home-manager

This setup allows **both** home-manager and VS Code to manage settings through a merge-based workflow.

## The Problem

By default, home-manager creates VS Code's `settings.json` as a **read-only symlink** to the Nix store, which prevents VS Code from making any runtime changes. This means:
- "Don't show again" dialogs can't persist
- VS Code can't save UI preferences
- Any runtime configuration changes are lost

## The Solution

We use a **home-manager activation script** that:
1. Creates a **writable** `settings.json` file (not a symlink)
2. Initializes it with our base settings on first run
3. On subsequent rebuilds, **merges** our structural settings with existing user settings
4. VS Code can freely modify the file between rebuilds

This gives you the best of both worlds: declarative management of critical settings + runtime flexibility.

## How It Works

### On First Home-Manager Rebuild
```
home-manager activation script runs
  ↓
Removes old symlink (if exists)
  ↓
Creates writable settings.json with base settings
  ↓
VS Code can now modify the file freely
```

### On Subsequent Rebuilds
```
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

### During Daily Use
```
VS Code makes changes → Writes to settings.json → Changes persist!
```

## Settings Categories

**Structural Settings** (managed by `vscode.nix`):
- Paths to formatters, language servers (e.g., `nix.serverPath`)
- Tool configurations that reference Nix store paths
- Core development workflow settings

**User Preferences** (can be modified by VS Code):
- UI theme and appearance
- Window state and zoom levels
- "Don't show again" dialogs
- Telemetry and update settings
- Extension-specific preferences

### The Workflow

```
┌──────────────────────────────────────────────────────────────┐
│ 1. Initial Rebuild                                            │
│    Activation script creates writable settings.json          │
│    Initializes with structural settings from vscode.nix      │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. Daily Usage                                                │
│    VS Code freely modifies settings.json                     │
│    Changes persist! (UI preferences, dialogs, etc.)          │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. Subsequent Rebuilds                                        │
│    Activation script runs again                               │
│    Merges: User settings + Updated structural settings       │
│    Your preferences preserved, paths updated                  │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. Optional: Sync to Nix (for multi-machine setup)          │
│    Run: ./scripts/sync-vscode-settings                        │
│    Captures user settings in vscode-user-settings.nix        │
│    Commit to share preferences across machines               │
└──────────────────────────────────────────────────────────────┘
```

## Usage

### Daily Use

**Just use VS Code normally!** Your changes will persist automatically:
- Click "Don't show again" on dialogs ✓
- Change UI preferences ✓
- Adjust editor settings ✓
- Configure extensions ✓

All changes are saved to `~/.config/Code/User/settings.json` and will persist across VS Code restarts **and** home-manager rebuilds.

### After Rebuilding

Your user preferences are automatically preserved. The activation script only updates the "structural" settings (paths to Nix store binaries).

### Optional: Syncing Settings to Nix (for multi-machine setups)

If you want to share your VS Code preferences across multiple machines, you can capture them in your Nix config:

```bash
./scripts/sync-vscode-settings
```

This will:
1. Read your current VS Code settings from `~/.config/Code/User/settings.json`
2. Filter out the structural settings managed by home-manager
3. Generate `home/modules/vscode-user-settings.nix` with your user preferences
4. The file is automatically imported by `vscode.nix`

### Review and Commit

```bash
# Review what changed
git diff home/modules/vscode-user-settings.nix

# Commit if you want to preserve these settings
git add home/modules/vscode-user-settings.nix
git commit -m "Update VS Code user preferences"

# Rebuild to apply (though this isn't strictly necessary since
# home-manager won't overwrite settings until next rebuild anyway)
./scripts/rebuild
```

## Configuration

The current setup in `vscode.nix`:

```nix
# Structural settings (always managed by home-manager)
vscodeNixSettings = {
  "editor.formatOnSave" = true;
  "[nix]" = {
    "editor.defaultFormatter" = "jnoortheen.nix-ide";
  };
  "nix.enableLanguageServer" = true;
  "nix.serverPath" = nilBin;  # Points to Nix store
  "nix.formatterPath" = alejandraBin;  # Points to Nix store
  # ...
};

# User settings (synced from VS Code)
vscodeUserSettings = 
  if builtins.pathExists ./vscode-user-settings.nix
  then (import ./vscode-user-settings.nix).userSettings
  else {};

# Both are merged together
allVscodeSettings = vscodeNixSettings // vscodeUserSettings;
```

### Adding More Structural Settings

Edit `home/modules/vscode.nix` and add to `vscodeNixSettings`:

```nix
vscodeNixSettings = {
  # ... existing settings ...
  
  # Add your own structural settings
  "python.defaultInterpreterPath" = "${pkgs.python3}/bin/python";
  "rust-analyzer.server.path" = "${pkgs.rust-analyzer}/bin/rust-analyzer";
};
```

Don't forget to add these keys to the filter list in `scripts_py/sync_vscode_settings.py`:

```python
def get_managed_keys() -> set[str]:
    return {
        "editor.formatOnSave",
        "[nix]",
        "nix.enableLanguageServer",
        # ... existing keys ...
        "python.defaultInterpreterPath",  # Add your keys here
        "rust-analyzer.server.path",
    }
```

## Important Notes

### How It Actually Works

The key innovation is **using a home-manager activation script instead of `programs.vscode.userSettings`**:

```nix
# Instead of this (creates read-only symlink):
programs.vscode.userSettings = { ... };

# We use this (creates writable file with smart merging):
home.activation.vscodeSettings = lib.hm.dag.entryAfter ["writeBoundary"] ''
  # Creates/updates writable settings.json
  # Merges user settings + structural settings
'';
```

### Settings Are Preserved Across Rebuilds

Unlike the default home-manager behavior (which overwrites settings.json), our activation script:
1. Checks if settings.json exists and is a regular file
2. If yes: Merges your existing settings with updated structural settings using `jq`
3. If no: Creates a new file with base settings

**This means VS Code changes persist automatically** - no manual syncing required for daily use!

### The Sync Script Is Optional

`./scripts/sync-vscode-settings` is only needed if you want to:
- Share your personalized settings across multiple machines via git
- Keep a declarative record of your preferences
- Review what settings have accumulated over time

For single-machine use, you can just let VS Code manage everything!

### Multi-Machine Setup

The generated `vscode-user-settings.nix` is machine-agnostic:
- Sync settings on your main machine
- Commit to git
- Other machines get the same user preferences
- But each machine can still make local changes (just sync them later)

### What Gets Filtered

The sync script filters out settings that:
1. Reference Nix store paths (these change across rebuilds)
2. Are explicitly listed in `get_managed_keys()`
3. Should always be managed declaratively

## Troubleshooting

### Settings.json is still a symlink

If after rebuilding, `~/.config/Code/User/settings.json` is still a symlink:

```bash
ls -la ~/.config/Code/User/settings.json
```

The activation script should have converted it. Try:
1. Manually remove the symlink: `rm ~/.config/Code/User/settings.json`
2. Rebuild: `./scripts/rebuild`
3. The activation script will create a writable file

### VS Code says settings are read-only

Check file permissions:
```bash
ls -la ~/.config/Code/User/settings.json
```

Should show: `-rw-r--r--` (regular file, readable/writable)

If it shows `lrwxrwxrwx` (symlink), see above.

### My settings disappear after rebuild

This shouldn't happen with the new activation script! The script specifically preserves existing settings.

If it does happen:
1. Check the activation script output during rebuild
2. Verify `jq` is available: `which jq`
3. Check the settings file before and after rebuild

### Structural settings not updating

If paths to formatters/LSP servers are stale after a Nix store update:
- Rebuild again: `./scripts/rebuild`  
- The activation script will overlay fresh structural settings

Default path: `~/.config/Code/User/settings.json`

If VS Code uses a different location:
- Check with: `code --version` and look for user data directory
- Update `get_vscode_settings_path()` in `scripts_py/sync_vscode_settings.py`

### I want to share some settings but not others

Edit `get_managed_keys()` to control what's filtered out. Keys in that set are always managed by Nix and never appear in the sync output.

## Alternative Approaches (Not Implemented)

### 1. Disable home-manager settings management entirely
**Pros**: VS Code has full control
**Cons**: Lose declarative benefits, no Nix store path management

### 2. Use separate settings files
**Pros**: Clean separation
**Cons**: VS Code doesn't natively support this

### 3. Automated git hooks
**Pros**: Automatic syncing
**Cons**: Noisy commits, merge conflicts

The sync-based approach gives you the best balance of declarative management and runtime flexibility.

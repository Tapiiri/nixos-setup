{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;

  # Keep VS Code settings in one place. We only apply them when VS Code is enabled
  # somewhere else (e.g. `my.devtools.enable` sets `programs.vscode.enable = true`).
  vscodeEnabled = config.programs.vscode.enable or false;

  # VS Code needs a path to the formatter binary for Nix files.
  alejandraBin = lib.getExe pkgs.alejandra;
  nilBin = lib.getExe pkgs.nil;

  # Extension IDs are `publisher.extensionName`.
  nixIdeExt = pkgs.vscode-extensions.jnoortheen.nix-ide;

  # Settings used by nix-ide / VS Code Nix tooling.
  # These are "structural" settings that point to binaries and configure tooling.
  # They should be managed declaratively by home-manager.
  vscodeNixSettings = {
    # Format on save globally.
    "editor.formatOnSave" = true;

    # Use alejandra for Nix formatting.
    "[nix]" = {
      "editor.defaultFormatter" = "jnoortheen.nix-ide";
    };

    # nix-ide settings.
    "nix.enableLanguageServer" = true;
    "nix.serverPath" = nilBin;
    "nix.formatterPath" = alejandraBin;

    # Helpful, conservative defaults.
    "nix.serverSettings" = {
      nil = {
        # nil supports formatting via external formatter.
        formatting = {command = [alejandraBin];};
      };
    };
  };

  # User-specific settings that VS Code may modify at runtime.
  # To capture VS Code's runtime changes and integrate them here,
  # run: ./scripts/sync-vscode-settings
  # This will generate vscode-user-settings.nix with any new settings.
  vscodeUserSettingsPath = ./vscode-user-settings.nix;
  vscodeUserSettings =
    if builtins.pathExists vscodeUserSettingsPath
    then (import vscodeUserSettingsPath).userSettings
    else {};

  # Merge structural and user settings
  # Note: home-manager will write these to settings.json on each rebuild,
  # overwriting any manual changes. To preserve manual changes, sync them
  # back to this Nix config using ./scripts/sync-vscode-settings
  allVscodeSettings = vscodeNixSettings // vscodeUserSettings;
in {
  options.my.vscode = {
    enable = mkEnableOption "VS Code configuration (extensions + settings)";
  };

  config = mkIf (config.my.vscode.enable && vscodeEnabled) {
    programs.vscode = {
      # We intentionally *don't* set `enable = true` here; devtools (or another module)
      # is responsible for that.

      # Allow VS Code to manage extensions directory (mutable)
      mutableExtensionsDir = true;

      # Install extensions using the new profiles syntax
      # but don't set userSettings (we manage via activation script)
      profiles.default.extensions = [nixIdeExt];
    };

    # Use an activation script to merge our base settings with any existing user settings
    # This allows VS Code to modify settings.json while we provide defaults
    home.activation.vscodeSettings = lib.hm.dag.entryAfter ["writeBoundary"] ''
            vscode_settings_file="$HOME/.config/Code/User/settings.json"
            vscode_settings_dir="$(dirname "$vscode_settings_file")"

            # Ensure the directory exists
            $DRY_RUN_CMD mkdir -p "$vscode_settings_dir"

            # If settings.json doesn't exist or is a symlink (from old home-manager config),
            # create/replace it with our base settings
            if [[ ! -f "$vscode_settings_file" ]] || [[ -L "$vscode_settings_file" ]]; then
              $DRY_RUN_CMD rm -f "$vscode_settings_file"
              $DRY_RUN_CMD cat > "$vscode_settings_file" <<'EOF'
      ${builtins.toJSON allVscodeSettings}
      EOF
              $VERBOSE_ECHO "VS Code settings initialized (writable file created)"
            else
              # File exists and is not a symlink - preserve it but ensure our structural settings are present
              # We use jq to merge, with our settings taking precedence for managed keys
              if command -v jq >/dev/null 2>&1; then
                managed_settings='${builtins.toJSON vscodeNixSettings}'
                current_settings=$(cat "$vscode_settings_file")

                # Merge: current settings as base, overlay our managed settings on top
                merged=$(echo "$current_settings" | ${pkgs.jq}/bin/jq --argjson managed "$managed_settings" '. + $managed')

                $DRY_RUN_CMD echo "$merged" > "$vscode_settings_file"
                $VERBOSE_ECHO "VS Code settings updated (structural settings enforced)"
              else
                $VERBOSE_ECHO "VS Code settings preserved (jq not available for merge)"
              fi
            fi
    '';
  };
}

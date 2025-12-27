{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;

  jsonFormat = pkgs.formats.json {};

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

    # Syntax highlighting for activation-script templates.
    # VS Code doesn't know what `*.tpl` is by default.
    "files.associations" = {
      "*.sh.tpl" = "shellscript";
    };

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
  # This will generate user-settings.nix with any new settings.
  vscodeUserSettingsPath = ./user-settings.nix;
  vscodeUserSettings =
    if builtins.pathExists vscodeUserSettingsPath
    then (import vscodeUserSettingsPath).userSettings
    else {};

  # Merge structural and user settings
  # Note: home-manager will write these to settings.json on each rebuild,
  # overwriting any manual changes. To preserve manual changes, sync them
  # back to this Nix config using ./scripts/sync-vscode-settings
  allVscodeSettings = vscodeNixSettings // vscodeUserSettings;

  # Generate a proper JSON file in the Nix store rather than embedding JSON
  # into the activation script. This keeps this module readable and makes the
  # "template" a real file.
  vscodeSettingsTemplate = jsonFormat.generate "vscode-settings.json" allVscodeSettings;

  vscodeManagedSettingsJson = builtins.toJSON vscodeNixSettings;

  vscodeSettingsActivationScript = pkgs.replaceVars ./activation-vscode-settings.sh.tpl {
    SETTINGS_TEMPLATE = "${vscodeSettingsTemplate}";
    MANAGED_SETTINGS_JSON = vscodeManagedSettingsJson;
    JQ_BIN = "${pkgs.jq}/bin/jq";
  };
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

      # Install extensions using the new profiles syntax.
      profiles.default.extensions = [nixIdeExt];

      # IMPORTANT: Do NOT set userSettings here.
      # Home Manager's VS Code module writes settings.json as a symlink into the
      # Nix store, which makes it read-only for VS Code.
      #
      # We manage settings.json ourselves via the activation script below.
    };

    # Use an activation script to merge our base settings with any existing user settings
    # This allows VS Code to modify settings.json while we provide defaults
    # Run *after* Home Manager's built-in VS Code profile activation, because
    # that step may (re)create settings.json as a Nix store symlink.
    # We then replace it with a writable file and merge managed settings.
    home.activation.vscodeSettings = lib.hm.dag.entryAfter ["vscodeProfiles"] ''
      # Delegate the actual activation logic to a real template file rendered by Nix.
      # shellcheck source=/dev/null
      source "${vscodeSettingsActivationScript}"
    '';
  };
}

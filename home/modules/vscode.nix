{ config, lib, pkgs, ... }:

let
  inherit (lib) mkEnableOption mkIf;

  # Keep VS Code settings in one place. We only apply them when VS Code is enabled
  # somewhere else (e.g. `my.devtools.enable` sets `programs.vscode.enable = true`).
  vscodeEnabled = (config.programs.vscode.enable or false);

  # VS Code needs a path to the formatter binary for Nix files.
  alejandraBin = lib.getExe pkgs.alejandra;
  nilBin = lib.getExe pkgs.nil;

  # Extension IDs are `publisher.extensionName`.
  nixIdeExt = pkgs.vscode-extensions.jnoortheen.nix-ide;

  # Settings used by nix-ide / VS Code Nix tooling.
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
        formatting = { command = [ alejandraBin ]; };
      };
    };
  };

in
{
  options.my.vscode.enable = mkEnableOption "VS Code configuration (extensions + settings)";

  config = mkIf (config.my.vscode.enable && vscodeEnabled) {
    programs.vscode = {
      # We intentionally *don't* set `enable = true` here; devtools (or another module)
      # is responsible for that.

      profiles.default = {
        extensions = [ nixIdeExt ];
        userSettings = vscodeNixSettings;
      };
    };
  };
}

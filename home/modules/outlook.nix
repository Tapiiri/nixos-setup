{
  config,
  lib,
  pkgs,
  flakeRoot,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.outlook.enable = mkEnableOption "Outlook desktop (outlook-for-linux)";

  config = mkIf config.my.outlook.enable {
    # Microsoft ships no Outlook desktop client for Linux. outlook-for-linux is
    # the Electron wrapper from the teams-for-linux maintainer; it is not in
    # nixpkgs, so we repackage the upstream .deb. Prefer this over
    # `my.outlookWeb` (a Chrome --app shortcut) where a real window, tray icon
    # and native notifications matter.
    home.packages = [
      (pkgs.callPackage (flakeRoot + "/pkgs/apps/outlook-for-linux.nix") {})
    ];
  };
}

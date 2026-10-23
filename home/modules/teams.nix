{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.teams.enable = mkEnableOption "Microsoft Teams (teams-for-linux)";

  config = mkIf config.my.teams.enable {
    # Microsoft no longer ships an official Teams desktop client for Linux.
    # teams-for-linux is the usual Electron wrapper packaged in nixpkgs.
    home.packages = [
      pkgs.teams-for-linux
    ];
  };
}

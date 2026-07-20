{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.moonlight.enable = mkEnableOption "Moonlight game streaming client";

  config = mkIf config.my.moonlight.enable {
    home.packages = [
      pkgs.moonlight-qt
    ];
  };
}

{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.affinity.enable = mkEnableOption "Affinity v3 (via Wine)";

  config = mkIf config.my.affinity.enable {
    home.packages = [pkgs.affinity-v3];
  };
}

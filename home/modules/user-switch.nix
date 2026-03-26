{
  config,
  lib,
  pkgs,
  flakeRoot,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.userSwitch.enable = mkEnableOption "User switch command (switch-user)";

  config = mkIf config.my.userSwitch.enable {
    home.packages = [
      flakeRoot.packages.${pkgs.system}."switch-user"
    ];
  };
}

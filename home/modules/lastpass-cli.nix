{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.lastpass-cli.enable = mkEnableOption "Lastpass password manager CLI";

  config = mkIf config.my.lastpass-cli.enable {
    home.packages = [
      pkgs.lastpass-cli
    ];
  };
}

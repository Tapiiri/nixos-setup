{
  config,
  lib,
  pkgs,
  flakeRoot,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.dokployCli = {
    enable = mkEnableOption "Dokploy CLI";
  };

  config = mkIf config.my.dokployCli.enable {
    home.packages = [
      (pkgs.callPackage (flakeRoot + "/pkgs/devtools/dokploy-cli.nix") {})
    ];
  };
}

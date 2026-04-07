{
  config,
  inputs,
  lib,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.affinity.enable = mkEnableOption "Affinity v3 (via Wine)";

  config = mkIf config.my.affinity.enable {
    home.packages = [
      inputs.affinity-nix.packages.x86_64-linux.v3
    ];
  };
}

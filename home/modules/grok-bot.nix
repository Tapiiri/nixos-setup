{
  config,
  lib,
  pkgs,
  flakeRoot,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.grok-bot.enable = mkEnableOption "Grok Bot desktop app (repackaged .deb)";

  config = mkIf config.my.grok-bot.enable {
    home.packages = [
      (pkgs.callPackage (flakeRoot + "/pkgs/apps/grok-bot.nix") {})
    ];
  };
}

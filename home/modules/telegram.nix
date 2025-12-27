{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.telegram.enable = mkEnableOption "Telegram Desktop";

  config = mkIf config.my.telegram.enable {
    home.packages = [
      pkgs.telegram-desktop
    ];
  };
}

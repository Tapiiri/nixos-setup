{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.cursor.enable = mkEnableOption "Cursor editor (code-cursor)";

  config = mkIf config.my.cursor.enable {
    home.packages = [
      pkgs.code-cursor
    ];
  };
}

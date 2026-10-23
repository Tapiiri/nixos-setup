{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.notion.enable = mkEnableOption "Notion desktop client";

  config = mkIf config.my.notion.enable {
    # Unofficial Linux desktop build (notion-enhancer repack). Official Notion
    # does not ship a first-party Linux client.
    home.packages = [
      pkgs.notion-app-enhanced
    ];
  };
}

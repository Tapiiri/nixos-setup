{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.slack.enable = mkEnableOption "Slack";

  config = mkIf config.my.slack.enable {
    home.packages = [
      pkgs.slack
    ];
  };
}

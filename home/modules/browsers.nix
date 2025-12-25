{ config, lib, ... }:

let
  inherit (lib) mkEnableOption mkIf;
in
{
  options.my.browsers.enable = mkEnableOption "Browsers (firefox + google-chrome)";

  config = mkIf config.my.browsers.enable {
    programs.firefox.enable = true;
    programs.google-chrome.enable = true;
  };
}

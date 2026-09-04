{
  config,
  lib,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.browsers.enable = mkEnableOption "Browsers (firefox + google-chrome)";

  config = mkIf config.my.browsers.enable {
    programs.firefox = {
      enable = true;
      # Silence the HM 26.05 configPath migration warning.
      # Keep the legacy path until profiles are migrated to XDG.
      configPath = ".mozilla/firefox";
    };
    programs.google-chrome.enable = true;
  };
}

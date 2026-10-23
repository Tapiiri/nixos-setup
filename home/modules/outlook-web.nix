{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf getExe;
in {
  options.my.outlookWeb.enable = mkEnableOption "Outlook on the web (Chrome app)";

  config = mkIf config.my.outlookWeb.enable {
    # Microsoft does not ship Outlook desktop for Linux. Pair this with
    # Thunderbird for a native IMAP/JMAP client; this entry covers Microsoft 365.
    xdg.desktopEntries.outlook = {
      name = "Outlook";
      genericName = "Email";
      comment = "Outlook on the web";
      exec = "${getExe pkgs.google-chrome} --app=https://outlook.office.com %U";
      icon = "mail-signed";
      categories = ["Network" "Email" "Office"];
      startupNotify = true;
      settings.StartupWMClass = "outlook.office.com";
    };
  };
}

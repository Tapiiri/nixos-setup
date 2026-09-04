{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf getExe;
in {
  options.my.linear.enable = mkEnableOption "Linear (Chrome app; no official Linux desktop client)";

  config = mkIf config.my.linear.enable {
    # Linear only ships macOS and Windows desktops. The supported Linux path is
    # the web app; wrap it as a Chrome --app window so it shows up in GNOME.
    xdg.desktopEntries.linear = {
      name = "Linear";
      genericName = "Issue tracker";
      comment = "Linear issue tracker (web app)";
      exec = "${getExe pkgs.google-chrome} --app=https://linear.app %U";
      icon = "web-browser";
      categories = ["Network" "Office"];
      startupNotify = true;
      settings.StartupWMClass = "linear.app";
    };
  };
}

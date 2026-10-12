{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.zellij.enable = mkEnableOption "Zellij terminal multiplexer";

  config = mkIf config.my.zellij.enable {
    # wl-clipboard provides wl-copy, referenced by copy_command below.
    home.packages = [pkgs.wl-clipboard];

    programs.zellij = {
      enable = true;
      enableBashIntegration = false;

      settings = {
        # Without copy_command, Zellij hands selections to the terminal via the
        # OSC 52 escape sequence. VTE (GNOME Console, GNOME Terminal) never
        # implemented OSC 52, so copies are silently dropped there. Piping to
        # wl-copy talks to the Wayland clipboard directly and works regardless
        # of terminal support.
        copy_command = "wl-copy";
      };
    };
  };
}

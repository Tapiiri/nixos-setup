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
    # wl-clipboard provides wl-copy, which Zellij uses as copy_command on Wayland.
    home.packages = [pkgs.wl-clipboard];

    programs.zellij = {
      enable = true;
      enableBashIntegration = config.my.shell.bash.enable;
    };
  };
}

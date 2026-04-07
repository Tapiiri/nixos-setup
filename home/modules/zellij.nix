{
  config,
  lib,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.zellij.enable = mkEnableOption "Zellij terminal multiplexer";

  config = mkIf config.my.zellij.enable {
    programs.zellij = {
      enable = true;
      enableBashIntegration = config.my.shell.bash.enable;
    };
  };
}

{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.tailscale.enable = mkEnableOption "Tailscale client (package)";

  config = mkIf config.my.tailscale.enable {
    # Install the tailscale CLI for user sessions via Home Manager.
    home.packages = with pkgs; [tailscale];
  };
}

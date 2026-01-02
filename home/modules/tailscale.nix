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
    # Note: `tailscale up` also requires the system daemon (tailscaled).
    # In this repo, enable that via the NixOS module: `my.tailscale.enable = true;`
    home.packages = with pkgs; [tailscale];
  };
}

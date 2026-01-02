{
  config,
  lib,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.tailscale.enable = mkEnableOption "Tailscale (system daemon)";

  config = mkIf config.my.tailscale.enable {
    # Run the system daemon (tailscaled). This is required for `tailscale up`
    # to work in the normal mode.
    services.tailscale.enable = true;
  };
}

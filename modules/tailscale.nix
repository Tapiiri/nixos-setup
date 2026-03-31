{
  config,
  lib,
  ...
}: let
  inherit (lib) mkAfter mkEnableOption mkIf mkOption types;
in {
  options.my.tailscale = {
    enable = mkEnableOption "Tailscale (system daemon)";

    operators = mkOption {
      type = types.listOf types.str;
      default = [];
      example = ["tapiiri" "ilmari"];
      description = "Users allowed to operate the local tailscaled daemon without sudo.";
    };
  };

  config = mkIf config.my.tailscale.enable {
    # Run the system daemon (tailscaled). This is required for `tailscale up`
    # to work in the normal mode.
    services.tailscale.enable = true;
    services.tailscale.extraUpFlags = mkAfter (
      map (operator: "--operator=${operator}") config.my.tailscale.operators
    );
    services.tailscale.extraSetFlags = mkAfter (
      map (operator: "--operator=${operator}") config.my.tailscale.operators
    );
  };
}

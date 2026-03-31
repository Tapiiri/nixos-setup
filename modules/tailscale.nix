{
  config,
  lib,
  ...
}: let
  inherit (lib) mkEnableOption mkIf mkOption types;
  cfg = config.my.tailscale;
in {
  options.my.tailscale = {
    enable = mkEnableOption "Tailscale (system daemon)";

    operator = mkOption {
      type = types.nullOr types.str;
      default = null;
      example = "ilmari";
      description = "Unix user allowed to operate tailscaled without sudo (only one supported by Tailscale).";
    };
  };

  config = mkIf cfg.enable {
    # Run the system daemon (tailscaled). This is required for `tailscale up`
    # to work in the normal mode.
    services.tailscale.enable = true;
    services.tailscale.extraSetFlags = lib.optionals (cfg.operator != null) [
      "--operator=${cfg.operator}"
    ];
  };
}

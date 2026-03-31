{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf mkMerge mkOption types;
  cfg = config.my.tailscale;
  funnelArgs =
    [
      "funnel"
      "--bg"
      "--yes"
    ]
    ++ lib.optionals (cfg.funnel.httpsPort != null) ["--https=${toString cfg.funnel.httpsPort}"]
    ++ lib.optionals (cfg.funnel.path != null) ["--set-path=${cfg.funnel.path}"]
    ++ [cfg.funnel.target];
in {
  options.my.tailscale = {
    enable = mkEnableOption "Tailscale (system daemon)";

    operator = mkOption {
      type = types.nullOr types.str;
      default = null;
      example = "ilmari";
      description = "Unix user allowed to operate tailscaled without sudo (only one supported by Tailscale).";
    };

    funnel = {
      enable = mkEnableOption "public Tailscale Funnel for a local service";

      target = mkOption {
        type = types.str;
        default = "http://127.0.0.1:3000";
        example = "http://127.0.0.1:3000";
        description = ''
          Local service target passed to `tailscale funnel`, such as a port,
          `host:port`, or URL.
        '';
      };

      httpsPort = mkOption {
        type = types.nullOr types.port;
        default = null;
        example = 443;
        description = ''
          Optional HTTPS port to expose with `tailscale funnel --https`.
          Leave null to use Tailscale's default HTTPS port behavior.
        '';
      };

      path = mkOption {
        type = types.nullOr types.str;
        default = null;
        example = "/dokploy";
        description = ''
          Optional path appended to the Funnel base URL via
          `tailscale funnel --set-path`.
        '';
      };
    };
  };

  config = mkIf cfg.enable (mkMerge [
    {
      # Run the system daemon (tailscaled). This is required for `tailscale up`
      # to work in the normal mode.
      services.tailscale.enable = true;
      services.tailscale.extraSetFlags = lib.optionals (cfg.operator != null) [
        "--operator=${cfg.operator}"
      ];
    }

    (mkIf cfg.funnel.enable {
      systemd.services.tailscale-funnel = {
        description = "Expose a local service through Tailscale Funnel";
        after = ["network-online.target" "tailscaled.service"];
        wants = ["network-online.target" "tailscaled.service"];
        wantedBy = ["multi-user.target"];
        partOf = ["tailscaled.service"];

        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
          Restart = "on-failure";
          RestartSec = "30s";
        };

        script = ''
          set -eu

          attempt=0
          while [ "$attempt" -lt 30 ]; do
            if ${pkgs.tailscale}/bin/tailscale status --json >/dev/null 2>&1; then
              exec ${pkgs.tailscale}/bin/tailscale ${lib.escapeShellArgs funnelArgs}
            fi

            sleep 2
            attempt=$((attempt + 1))
          done

          exec ${pkgs.tailscale}/bin/tailscale ${lib.escapeShellArgs funnelArgs}
        '';
      };
    })
  ]);
}

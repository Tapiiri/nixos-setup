{
  lib,
  config,
  ...
}: let
  cfg = config.my.rebuild;

  inherit (lib) mkEnableOption mkIf mkOption types optionalString;

  confText =
    ''
      [rebuild]
    ''
    + optionalString (cfg.upstreamUrl != null && cfg.upstreamUrl != "") ''
      upstream_url = ${cfg.upstreamUrl}
    ''
    + optionalString cfg.offlineOk ''
      offline_ok = true
    ''
    + ''
      mirror_dir = ${cfg.mirrorDir}
      ref = ${cfg.ref}
    '';
in {
  options.my.rebuild = {
    enable = mkEnableOption "Generate /etc/nixos-setup/rebuild.conf for the rebuild helper";

    upstreamUrl = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = ''
        Upstream Git URL used to create the bare mirror if it doesn't exist yet.

        If unset, the rebuild tool can still work if the upstream is provided via
        `NIXOS_SETUP_REBUILD_UPSTREAM_URL` or `--upstream-url`.
      '';
    };

    mirrorDir = mkOption {
      type = types.str;
      default = "/var/lib/nixos-setup/mirror.git";
      description = "Path to the bare mirror repository.";
    };

    ref = mkOption {
      type = types.str;
      default = "origin/main";
      description = "Git ref to fast-forward /etc/nixos to in mirror mode.";
    };

    offlineOk = mkOption {
      type = types.bool;
      default = false;
      description = "Default offline behavior for rebuild (same as --offline-ok).";
    };
  };

  config = mkIf cfg.enable {
    environment.etc."nixos-setup/rebuild.conf".text = confText;
  };
}

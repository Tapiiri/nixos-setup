{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf mkOption types;
  cfg = config.my.dokploy;
in {
  options.my.dokploy = {
    enable = mkEnableOption "Dokploy local service";

    users = mkOption {
      type = types.listOf types.str;
      default = [];
      description = ''
        User accounts that should be added to the `docker` group so they can
        inspect and manage the local Dokploy Docker setup without sudo.
      '';
    };

    passwordFile = mkOption {
      type = types.str;
      default = "/var/lib/secrets/dokploy-db-password";
      description = ''
        Root-readable file containing the Dokploy PostgreSQL password.
      '';
    };
  };

  config = mkIf cfg.enable {
    virtualisation.docker = {
      enable = true;
      daemon.settings.live-restore = false;
    };

    services.dokploy = {
      enable = true;
      port = lib.mkDefault "127.0.0.1:3000:3000";
      database.passwordFile = cfg.passwordFile;
      swarm.advertiseAddress = lib.mkDefault "private";
    };

    systemd.tmpfiles.rules = [
      "d /var/lib/secrets 0700 root root - -"
    ];

    system.activationScripts.dokployPassword = lib.stringAfter ["etc"] ''
      password_file=${lib.escapeShellArg cfg.passwordFile}

      if [ ! -f "$password_file" ]; then
        dir="$(${pkgs.coreutils}/bin/dirname "$password_file")"
        ${pkgs.coreutils}/bin/install -d -m 700 "$dir"

        tmp="$(${pkgs.coreutils}/bin/mktemp)"
        trap '${pkgs.coreutils}/bin/rm -f "$tmp"' EXIT
        ${pkgs.coreutils}/bin/head -c 32 /dev/urandom | ${pkgs.coreutils}/bin/base64 > "$tmp"
        ${pkgs.coreutils}/bin/install -m 600 "$tmp" "$password_file"
      fi
    '';

    users.users = lib.genAttrs cfg.users (_user: {
      extraGroups = ["docker"];
    });
  };
}

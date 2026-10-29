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

  # glibc major.minor versions in a system closure. New GLIBC_x.y symbol
  # versions only appear on a minor bump, so patch releases (2.42-51 ->
  # 2.42-67) and same-version rebuilds cannot break PAM and are ignored.
  glibcVersions = system: ''
    ${config.nix.package}/bin/nix-store -qR ${system} \
      | sed -nE 's|^/nix/store/[a-z0-9]{32}-(glibc-[0-9]+\.[0-9]+)[0-9.]*(-[0-9]+)?$|\1|p' \
      | sort -u
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

    # switch-to-configuration does not restart display-manager.service, so a
    # running GDM keeps the booted glibc while /etc/pam.d starts pointing at
    # PAM modules built against the new one. dlopen then fails with
    # "version `GLIBC_x.y' not found", pam_unix is dropped as a faulty module,
    # and every password and fingerprint login is rejected until a reboot.
    # Compare against the booted system rather than the previous generation,
    # so the warning repeats on every switch until the machine is rebooted.
    # At boot /run/booted-system does not exist yet, so this stays silent.
    system.activationScripts.glibcChangeWarning = ''
      if [ -e /run/booted-system ]; then
        booted_glibc=$(${glibcVersions "/run/booted-system"})
        new_glibc=$(${glibcVersions "\"$systemConfig\""})
        if [ -n "$booted_glibc" ] && [ "$booted_glibc" != "$new_glibc" ]; then
          {
            echo
            echo "warning: glibc changed since boot ($(echo $booted_glibc) -> $(echo $new_glibc))."
            echo "warning: GDM keeps running on the old glibc and cannot load the new PAM modules,"
            echo "warning: so logins and user switching will fail. Reboot before logging out or"
            echo "warning: switching users (or restart display-manager.service, which ends GUI sessions)."
            echo
          } >&2
        fi
      fi
    '';
  };
}

# NixOS module: QEMU test host support for shared-infra boot tests
#
# Provides the host-side prerequisites documented in shared-infra ADR-002:
#   - kvm group membership for /dev/kvm access (hardware-accelerated emulation)
#   - Persistent tap-qemu TAP interface at 192.168.100.1/24, owned by the
#     first configured user so QEMU can attach without CAP_NET_ADMIN
#
# The QEMU guest is expected at 192.168.100.2 (see ADR-002 timeout table).
# NetworkManager is told to leave tap-qemu unmanaged.
#
# Usage in host config:
#   my.qemu-test-host.enable = true;
#   my.qemu-test-host.users = [ "tapiiri" ];
{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf mkOption types;
  cfg = config.my.qemu-test-host;
in {
  options.my.qemu-test-host = {
    enable = mkEnableOption "QEMU test host support (TAP networking + KVM access) for shared-infra boot tests";

    users = mkOption {
      type = types.listOf types.str;
      default = [];
      description = ''
        User accounts to add to the `kvm` group for /dev/kvm access.
        The first user in the list becomes the owner of the tap-qemu TAP
        device, allowing QEMU to open /dev/net/tun without CAP_NET_ADMIN.
      '';
    };
  };

  config = mkIf cfg.enable {
    assertions = [
      {
        assertion = cfg.users != [];
        message = "my.qemu-test-host.users must contain at least one user";
      }
    ];

    # Add users to the kvm group for /dev/kvm access.
    users.groups.kvm = {};
    users.users = lib.genAttrs cfg.users (_user: {
      extraGroups = ["kvm"];
    });

    # Persistent TAP device for QEMU boot tests.
    # Host side: 192.168.100.1/24.  Guest expected at 192.168.100.2 (ADR-002).
    # Owned by the first user in cfg.users so QEMU can open /dev/net/tun
    # without requiring CAP_NET_ADMIN on the qemu-system-x86_64 binary.
    systemd.services.qemu-tap-setup = {
      description = "TAP device for QEMU boot tests (shared-infra)";
      wantedBy = ["multi-user.target"];
      after = ["network.target"];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        ExecStart = pkgs.writeShellScript "qemu-tap-up" ''
          set -euo pipefail
          if ! ${pkgs.iproute2}/bin/ip link show tap-qemu &>/dev/null; then
            ${pkgs.iproute2}/bin/ip tuntap add mode tap name tap-qemu \
              user ${lib.head cfg.users}
          fi
          # Idempotent: silently succeeds if address is already assigned.
          ${pkgs.iproute2}/bin/ip addr add 192.168.100.1/24 dev tap-qemu \
            2>/dev/null || true
          ${pkgs.iproute2}/bin/ip link set tap-qemu up
        '';
        ExecStop = pkgs.writeShellScript "qemu-tap-down" ''
          ${pkgs.iproute2}/bin/ip link set tap-qemu down 2>/dev/null || true
          ${pkgs.iproute2}/bin/ip tuntap del mode tap name tap-qemu 2>/dev/null || true
        '';
      };
    };

    # Prevent NetworkManager from claiming the tap-qemu interface.
    networking.networkmanager.unmanaged = ["tap-qemu"];
  };
}

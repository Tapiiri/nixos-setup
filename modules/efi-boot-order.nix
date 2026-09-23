# Keep a preferred EFI boot entry at the front of the firmware BootOrder.
#
# On the fw16 the root filesystem lives on a USB4/Thunderbolt NVMe enclosure,
# while the internal disk carries Windows. The firmware ships BootOrder with
# Windows Boot Manager first and the enclosure last, so every boot needs a
# manual override in the boot menu — easy to fat-finger straight into Windows.
#
# Putting the enclosure first gives the behaviour we actually want for free:
# UEFI skips boot entries whose device is absent, so the enclosure boots when
# it is plugged in and Windows boots when it is not. No fallback logic needed.
#
# This runs on every boot rather than once at install time because Windows
# Update and the firmware's own boot-entry housekeeping both rewrite BootOrder
# behind our back. Entries are matched by label, not by Boot#### number, since
# firmware-generated "EFI Hard Drive (...)" entries get renumbered whenever the
# device is re-enumerated.
{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) concatStringsSep escapeShellArg mkEnableOption mkIf mkOption types;
  cfg = config.my.efiBootOrder;
in {
  options.my.efiBootOrder = {
    enable = mkEnableOption "asserting a preferred EFI boot entry at boot";

    preferMatching = mkOption {
      type = types.listOf types.str;
      default = [];
      example = ["Linux Boot Manager" "Corsair MP600 ELITE"];
      description = ''
        Boot entry labels to promote to the front of BootOrder, as POSIX
        extended regular expressions matched against `efibootmgr` output.

        Patterns are tried in order and the first one that matches an existing
        entry wins, so list the most specific preference first. If nothing
        matches, BootOrder is left untouched.
      '';
    };
  };

  config = mkIf cfg.enable {
    assertions = [
      {
        assertion = cfg.preferMatching != [];
        message = "my.efiBootOrder.enable requires at least one pattern in my.efiBootOrder.preferMatching.";
      }
    ];

    systemd.services.efi-boot-order = {
      description = "Assert preferred EFI boot entry order";
      wantedBy = ["multi-user.target"];

      # efivarfs is mounted by systemd well before multi-user.target, but guard
      # anyway so a legacy-boot or container build degrades to a no-op.
      unitConfig.ConditionPathExists = "/sys/firmware/efi/efivars";

      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
      };

      script = let
        patterns = concatStringsSep " " (map escapeShellArg cfg.preferMatching);
      in ''
        set -euo pipefail

        efibootmgr=${lib.getExe' pkgs.efibootmgr "efibootmgr"}
        listing=$("$efibootmgr")

        current=$(printf '%s\n' "$listing" | sed -n 's/^BootOrder: //p')
        if [ -z "$current" ]; then
          echo "no BootOrder variable present; leaving firmware boot order alone"
          exit 0
        fi

        target=""
        for pattern in ${patterns}; do
          # Match only real entry lines (Boot0001* Label), never BootOrder/BootCurrent.
          target=$(printf '%s\n' "$listing" \
            | grep -E "^Boot[0-9A-Fa-f]{4}\*?[[:space:]]" \
            | grep -E -- "$pattern" \
            | head -n1 \
            | sed -E 's/^Boot([0-9A-Fa-f]{4}).*/\1/')
          if [ -n "$target" ]; then
            echo "matched boot entry Boot$target via pattern: $pattern"
            break
          fi
        done

        if [ -z "$target" ]; then
          echo "no boot entry matched; leaving BootOrder as $current"
          exit 0
        fi

        if [ "''${current%%,*}" = "$target" ]; then
          echo "Boot$target already first in BootOrder; nothing to do"
          exit 0
        fi

        # Rebuild the order with the target first, preserving every other entry
        # in its existing relative position.
        rest=$(printf '%s' "$current" \
          | tr ',' '\n' \
          | grep -v -x -- "$target" \
          | paste -sd, -)

        if [ -n "$rest" ]; then
          new="$target,$rest"
        else
          new="$target"
        fi

        echo "setting BootOrder: $current -> $new"
        "$efibootmgr" -o "$new" >/dev/null
      '';
    };
  };
}

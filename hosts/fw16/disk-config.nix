# Declarative disk layout for the FW16 USB 4 NVMe enclosure.
#
# Partition scheme:  GPT → 512 MiB EFI + LUKS-encrypted root (ext4)
#
# The device path is `lib.mkDefault` so it can be overridden at install
# time without editing this file. If `lsblk` on the installer shows
# something other than /dev/nvme0n1, create a one-line override module
# (e.g. /tmp/disk-override.nix) and include it when installing:
#
#   { ... }: { disko.devices.disk.main.device = "/dev/sda"; }
#
# Then: sudo nixos-install --flake <local-clone>#fw16 \
#           --option extra-substituters ... etc.
# (Using a local clone of this repo where /tmp/disk-override.nix is
# imported from hosts/fw16/configuration.nix.)
{lib, ...}: {
  disko.devices = {
    disk = {
      main = {
        type = "disk";
        device = lib.mkDefault "/dev/nvme0n1";
        content = {
          type = "gpt";
          partitions = {
            ESP = {
              size = "512M";
              type = "EF00";
              content = {
                type = "filesystem";
                format = "vfat";
                mountpoint = "/boot";
                mountOptions = ["fmask=0077" "dmask=0077"];
              };
            };
            luks = {
              size = "100%";
              content = {
                type = "luks";
                name = "cryptroot";
                settings = {
                  # TRIM pass-through — safe for NVMe, recoverable if needed.
                  allowDiscards = true;
                };
                content = {
                  type = "filesystem";
                  format = "ext4";
                  mountpoint = "/";
                };
              };
            };
          };
        };
      };
    };
  };
}

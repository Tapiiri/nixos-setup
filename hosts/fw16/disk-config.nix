# Declarative disk layout for the FW16 USB 4 NVMe enclosure.
#
# Partition scheme:  GPT → 512 MiB EFI + LUKS-encrypted root (ext4)
#
# The device name depends on how the USB 4 enclosure enumerates at boot.
# Adjust `device` below if `lsblk` shows a different path on the FW16
# (e.g. /dev/sda when using UAS, /dev/nvme1n1 if an internal drive is present).
{
  disko.devices = {
    disk = {
      main = {
        type = "disk";
        device = "/dev/nvme0n1";
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

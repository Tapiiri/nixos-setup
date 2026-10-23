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

                  # Do not leave the LUKS passphrase in the kernel keyring
                  # after boot. systemd-cryptsetup caches it there as the
                  # `user` key named "cryptsetup" so it can reuse it across
                  # volumes; we only have one, so the cache buys nothing.
                  #
                  # It is not inert: gdm's pam_gdm.so looks that key up
                  # (find_key_by_type_and_desc("user", "cryptsetup", 0)) and
                  # sets it as PAM_AUTHTOK on fingerprint logins, which hands
                  # the full-disk-encryption passphrase to gnome-keyring as a
                  # candidate keyring password. See the matching comment on
                  # security.pam.services.login.enableGnomeKeyring in
                  # hosts/common/system.nix.
                  #
                  # password-cache= is systemd >= 254; this host runs 261.
                  crypttabExtraOpts = ["password-cache=no"];
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

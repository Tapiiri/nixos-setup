# PLACEHOLDER — replace before installation.
#
# On the FW16, after partitioning and mounting the NVMe at /mnt:
#   nixos-generate-config --root /mnt
# Copy the generated /mnt/etc/nixos/hardware-configuration.nix here,
# then commit and proceed with nixos-install.
#
# The nixos-hardware framework-16-7040-amd module (imported in configuration.nix)
# handles AMD microcode, Mesa/RADV, suspend fixes, and power management — those
# do not need to be repeated here.
{
  lib,
  modulesPath,
  ...
}: {
  imports = [(modulesPath + "/installer/scan/not-detected.nix")];

  boot.initrd.availableKernelModules = ["xhci_pci" "nvme" "uas" "usb_storage" "sd_mod"];
  boot.initrd.kernelModules = [];
  boot.kernelModules = ["kvm-amd"];
  boot.extraModulePackages = [];

  # Stub UUIDs — required for flake evaluation. Replace with output of
  # nixos-generate-config when installing. Do NOT use these for an actual install.
  fileSystems."/" = {
    device = "/dev/disk/by-uuid/00000000-0000-0000-0000-000000000001";
    fsType = "ext4";
  };

  fileSystems."/boot" = {
    device = "/dev/disk/by-uuid/0000-0001";
    fsType = "vfat";
    options = ["fmask=0077" "dmask=0077"];
  };

  swapDevices = [];

  networking.useDHCP = lib.mkDefault true;
  nixpkgs.hostPlatform = lib.mkDefault "x86_64-linux";
}

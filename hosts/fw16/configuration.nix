{
  inputs,
  lib,
  ...
}: {
  imports =
    [
      inputs.nixos-hardware.nixosModules.framework-16-7040-amd
      inputs.disko.nixosModules.disko
      ../common/system.nix
      ./disk-config.nix
      ./hardware-configuration.nix
    ]
    # Optional install-time override: the installer's fw16-install script
    # writes hosts/fw16/local-device.nix with a non-default disk device when
    # the NVMe enclosure enumerates as something other than /dev/nvme0n1.
    ++ lib.optional (builtins.pathExists ./local-device.nix) ./local-device.nix;

  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  networking.hostName = "fw16";

  # Set to the NixOS version used for the initial install.
  system.stateVersion = "25.05";
}

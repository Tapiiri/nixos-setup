{
  inputs,
  lib,
  pkgs,
  ...
}: {
  imports =
    [
      inputs.nixos-hardware.nixosModules.framework-16-7040-amd
      inputs.disko.nixosModules.disko
      inputs.lanzaboote.nixosModules.lanzaboote
      ../common/system.nix
      ./disk-config.nix
      ./hardware-configuration.nix
    ]
    # Optional install-time override: the installer's fw16-install script
    # writes hosts/fw16/local-device.nix with a non-default disk device when
    # the NVMe enclosure enumerates as something other than /dev/nvme0n1.
    ++ lib.optional (builtins.pathExists ./local-device.nix) ./local-device.nix;

  # Lanzaboote takes over from systemd-boot to sign EFI binaries so
  # Secure Boot works alongside Windows (Microsoft keys are kept when
  # enrolling via `sbctl enroll-keys --microsoft`).
  boot.loader.systemd-boot.enable = lib.mkForce false;
  boot.lanzaboote = {
    enable = true;
    pkiBundle = "/etc/secureboot";
  };
  boot.loader.efi.canTouchEfiVariables = true;

  environment.systemPackages = [pkgs.sbctl];

  networking.hostName = "fw16";

  # Set to the NixOS version used for the initial install.
  system.stateVersion = "25.05";
}

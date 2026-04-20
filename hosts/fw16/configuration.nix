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
    pkiBundle = "/var/lib/sbctl";
  };
  boot.loader.efi.canTouchEfiVariables = true;

  # Work around USB4/Thunderbolt PCIe tunneling I/O errors with the HYPER
  # enclosure — prevents the host from resetting the Thunderbolt controller,
  # which can drop NVMe transactions mid-flight.
  boot.kernelParams = ["thunderbolt.host_reset=0"];

  environment.systemPackages = [pkgs.sbctl];

  # Disable USB autosuspend for the HYPER USB4 NVMe enclosure (339a:1701).
  # Linux's aggressive USB power management can suspend the enclosure mid-mount,
  # causing dirty-unmount EXT4 journal corruption identical to a hot-unplug.
  services.udev.extraRules = ''
    ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="339a", ATTR{idProduct}=="1701", ATTR{power/autosuspend_delay_ms}="-1"
  '';

  networking.hostName = "fw16";

  # Set to the NixOS version used for the initial install.
  system.stateVersion = "25.05";
}

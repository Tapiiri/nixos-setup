{inputs, ...}: {
  imports = [
    inputs.nixos-hardware.nixosModules.framework-16-7040-amd
    ../common/system.nix
    ./hardware-configuration.nix
  ];

  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  networking.hostName = "fw16";

  # Set to the NixOS version used for the initial install.
  system.stateVersion = "25.05";
}

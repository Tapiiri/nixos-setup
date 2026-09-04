{...}: {
  imports = [
    ../common/system.nix
    ./hardware-configuration.nix
  ];

  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  networking.hostName = "fw12";

  system.stateVersion = "25.05";
}

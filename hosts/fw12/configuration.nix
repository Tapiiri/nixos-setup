{inputs, ...}: {
  imports = [
    ../common/system.nix
    ./hardware-configuration.nix
    inputs.vaisala-pilot.nixosModules.devHost
  ];

  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  networking.hostName = "fw12";

  vaisala.devHost = {
    enable = true;
    user = "tapiiri";
    # codeRoot defaults to /home/tapiiri/Koodit
  };

  system.stateVersion = "25.05";
}

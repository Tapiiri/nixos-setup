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
    users = ["tapiiri" "ilmari"];
    # codeRoot defaults to ~/Koodit for each user
    # Migrations run against whichever checkout has .sql files at service-start time.
  };

  system.stateVersion = "25.05";
}

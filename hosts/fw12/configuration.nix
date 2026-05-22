{inputs, ...}: {
  imports = [
    ../common/system.nix
    ./hardware-configuration.nix
    inputs.vaisala-pilot.nixosModules.devHost
    inputs.xtdb-test.nixosModules.devHost
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
  vaisala.localDev.atexEngineBin = "/nix/store/d4gyz5l7cxmj10vjzvmvnz7kpfdhh8ys-atex-engine-0.1.0/bin/atex-engine";

  catalys.devHost = {
    enable = true;
    users = ["tapiiri" "ilmari"];
  };

  system.stateVersion = "25.05";
}

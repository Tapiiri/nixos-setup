{...}: {
  imports = [
    ../common/system.nix
    ./hardware-configuration.nix
  ];

  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  networking.hostName = "nixos";

  vaisala.devHost = {
    enable = true;
    user = "tapiiri";
    # codeRoot defaults to /home/tapiiri/Koodit
  };

  system.stateVersion = "25.05";
}

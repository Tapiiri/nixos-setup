{inputs, ...}: {
  imports = [
    ../common/system.nix
    ./hardware-configuration.nix
    inputs.vaisala-pilot.nixosModules.devHost
    inputs.xtdb-test.nixosModules.devHost
    inputs.document-ingest-proto.nixosModules.devHost
  ];

  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  networking.hostName = "fw12";

  # ── Project specialisations ──────────────────────────────────────
  # Each project owns its full service stack. Switch with:
  #   sudo /run/current-system/specialisation/<name>/bin/switch-to-configuration switch
  # Return to base (no project services):
  #   sudo /run/current-system/bin/switch-to-configuration switch
  specialisation = {
    vaisala.configuration = {
      vaisala.devHost = {
        enable = true;
        users = ["tapiiri" "ilmari"];
      };
      vaisala.localDev.atexEngineBin = "/nix/store/d4gyz5l7cxmj10vjzvmvnz7kpfdhh8ys-atex-engine-0.1.0/bin/atex-engine";
    };

    catalys.configuration = {
      catalys.devHost = {
        enable = true;
        users = ["tapiiri" "ilmari"];
      };
    };

    document-ingest.configuration = {
      document-ingest.devHost = {
        enable = true;
        users = ["tapiiri" "ilmari"];
      };
    };
  };

  system.stateVersion = "25.05";
}

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

    guest.configuration = {
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

    # shared-infra: enables the QEMU boot-test prerequisites from ADR-002.
    # Provides tap-qemu (192.168.100.1/24) and /dev/kvm access for tapiiri.
    # Required before running `just test-image` in the shared-infra devShell.
    shared-infra.configuration = {
      my.qemu-test-host = {
        enable = true;
        users = ["tapiiri"];
      };
    };
  };

  system.stateVersion = "25.05";
}

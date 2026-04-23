# Base developer machine configuration — used by CI to pre-build and cache
# the shared closure. All developer hosts (nixos/fw12, fw16, …) extend this.
#
# No hardware-specific config, no private project dependencies.
# Build with: nix build .#nixosConfigurations.base.config.system.build.toplevel
{...}: {
  imports = [
    ../common/system.nix
  ];

  nixpkgs.hostPlatform = "x86_64-linux";

  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  networking.hostName = "base";

  # Stub root filesystem — satisfies the NixOS module check.
  # This host is never installed on real hardware.
  fileSystems."/" = {
    device = "/dev/disk/by-label/nixos";
    fsType = "ext4";
  };

  system.stateVersion = "25.05";
}

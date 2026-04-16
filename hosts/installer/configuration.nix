# NixOS installer image, pre-baked with this flake and an interactive
# fw16-install helper. Build with:
#
#   nix build .#installer-iso
#
# The resulting ISO is at ./result/iso/nixos-*.iso — flash to USB with dd.
{
  config,
  lib,
  pkgs,
  modulesPath,
  inputs,
  ...
}: let
  diskoPkg = inputs.disko.packages.${pkgs.stdenv.hostPlatform.system}.disko;

  fw16-install = pkgs.writeShellScriptBin "fw16-install" ''
    set -euo pipefail

    FLAKE_SRC="/etc/nixos-setup-flake"
    HOST="fw16"
    DEFAULT_DEVICE="/dev/nvme0n1"

    echo "=================================================="
    echo "  Tapiiri NixOS installer — Framework 16 target"
    echo "=================================================="
    echo
    echo "Block devices currently visible:"
    lsblk -o NAME,SIZE,TYPE,FSTYPE,TRAN,MODEL
    echo

    read -rp "Target device for install [$DEFAULT_DEVICE]: " DEVICE
    DEVICE="''${DEVICE:-$DEFAULT_DEVICE}"

    if [[ ! -b "$DEVICE" ]]; then
      echo "ERROR: $DEVICE is not a block device" >&2
      exit 1
    fi

    echo
    echo "*** WARNING: All data on $DEVICE will be destroyed. ***"
    read -rp "Type YES to confirm: " CONFIRM
    [[ "$CONFIRM" == "YES" ]] || { echo "Aborted."; exit 1; }

    # Make a writable copy of the flake (the baked-in one lives in the
    # read-only nix store).
    WORK=$(mktemp -d -t nixos-setup-XXXXXX)
    cp -r "$FLAKE_SRC"/. "$WORK/"
    chmod -R u+w "$WORK"
    cd "$WORK"

    # Write device override if user picked something other than default.
    if [[ "$DEVICE" != "$DEFAULT_DEVICE" ]]; then
      cat > hosts/fw16/local-device.nix <<EOF
    {...}: {
      disko.devices.disk.main.device = "$DEVICE";
    }
    EOF
      echo "Wrote hosts/fw16/local-device.nix with device = $DEVICE"
    fi

    echo
    echo "==> Partitioning and formatting with disko..."
    sudo ${diskoPkg}/bin/disko \
      --mode destroy,format,mount \
      --flake ".#$HOST"

    echo
    echo "==> Running nixos-install (this may take a while)..."
    sudo nixos-install --no-root-passwd --flake ".#$HOST"

    echo
    echo "=================================================="
    echo "  Install complete."
    echo
    echo "  Set user passwords before rebooting:"
    echo "    sudo nixos-enter --root /mnt -c 'passwd tapiiri'"
    echo "    sudo nixos-enter --root /mnt -c 'passwd ilmari'"
    echo
    echo "  Then: sudo reboot"
    echo "=================================================="
  '';
in {
  imports = [
    (modulesPath + "/installer/cd-dvd/installation-cd-minimal.nix")
    (modulesPath + "/installer/cd-dvd/channel.nix")
  ];

  # Latest kernel — the minimal installer ships an older LTS that may not
  # have full Framework 16 AMD support out of the box.
  boot.kernelPackages = pkgs.linuxPackages_latest;

  # NetworkManager with nmtui for wifi setup.
  # wpa_supplicant must stay enabled — NM uses it as its WiFi backend.
  networking.networkmanager.enable = true;

  environment.systemPackages = with pkgs; [
    git
    vim
    tmux
    parted
    gptfdisk
    cryptsetup
    pciutils
    usbutils
    wget
    diskoPkg
    fw16-install
  ];

  # SSH available for headless / remote-driven installs.
  services.openssh = {
    enable = true;
    settings.PermitRootLogin = "yes";
  };

  # Pre-bake the flake source onto the ISO at a stable path.
  environment.etc."nixos-setup-flake".source = inputs.self;

  users.motd = ''

    ==================================================
     Tapiiri NixOS Installer  (Framework 16 target)
    ==================================================

     Pre-baked flake:  /etc/nixos-setup-flake
     Helper:           fw16-install

     Quick install:
       1) nmtui                  (connect to wifi)
       2) Plug in NVMe enclosure
       3) fw16-install           (interactive installer)

    ==================================================
  '';

  nix.settings = {
    experimental-features = ["nix-command" "flakes"];
    substituters = [
      "https://cache.nixos.org"
      "https://tapiiri-nixos-setup.cachix.org"
      "https://nix-community.cachix.org"
    ];
    trusted-public-keys = [
      "cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY="
      "tapiiri-nixos-setup.cachix.org-1:wBjh1nFp9lCRgdt6eOMPEv14KIE51cjYW0VczdgKYEU="
      "nix-community.cachix.org-1:mB9FSh9qf2dCimDSUo8Zy7bkq5CX+/rkCWyvRCUSeBc="
    ];
  };

  system.stateVersion = "25.05";
}

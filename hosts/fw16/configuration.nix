{
  inputs,
  lib,
  pkgs,
  ...
}: {
  imports =
    [
      inputs.nixos-hardware.nixosModules.framework-16-7040-amd
      inputs.disko.nixosModules.disko
      inputs.lanzaboote.nixosModules.lanzaboote
      ../common/system.nix
      ./disk-config.nix
      ./hardware-configuration.nix
    ]
    # Optional install-time override: the installer's fw16-install script
    # writes hosts/fw16/local-device.nix with a non-default disk device when
    # the NVMe enclosure enumerates as something other than /dev/nvme0n1.
    ++ lib.optional (builtins.pathExists ./local-device.nix) ./local-device.nix;

  # Lanzaboote takes over from systemd-boot to sign EFI binaries so
  # Secure Boot works alongside Windows (Microsoft keys are kept when
  # enrolling via `sbctl enroll-keys --microsoft`).
  boot.loader.systemd-boot.enable = lib.mkForce false;
  boot.lanzaboote = {
    enable = true;
    pkiBundle = "/var/lib/sbctl";
  };
  boot.loader.efi.canTouchEfiVariables = true;

  # Boot the enclosure by default instead of the internal Windows disk.
  #
  # The firmware has never created a "Linux Boot Manager" NVRAM entry for this
  # machine — it boots through its own auto-generated "EFI Hard Drive (...)"
  # entry via the ESP's \EFI\BOOT\BOOTX64.EFI fallback — so both labels are
  # listed, most specific first, and matched as regexes at boot time.
  #
  # Windows stays in BootOrder behind this entry, which is what makes pulling
  # the enclosure fall back to Windows automatically.
  my.efiBootOrder = {
    enable = true;
    preferMatching = ["Linux Boot Manager" "Corsair MP600 ELITE"];
  };

  # Work around USB4/Thunderbolt PCIe tunneling I/O errors with the HYPER
  # enclosure — prevents the host from resetting the Thunderbolt controller,
  # which can drop NVMe transactions mid-flight.
  boot.kernelParams = ["thunderbolt.host_reset=0"];

  environment.systemPackages = [pkgs.sbctl];

  # Disable USB autosuspend for the HYPER USB4 NVMe enclosure (339a:1701).
  # Linux's aggressive USB power management can suspend the enclosure mid-mount,
  # causing dirty-unmount EXT4 journal corruption identical to a hot-unplug.
  services.udev.extraRules = ''
    ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="339a", ATTR{idProduct}=="1701", ATTR{power/autosuspend_delay_ms}="-1"
  '';

  # Fingerprint reader (Goodix 27c6:609c on the Framework 16 power button).
  # Driven by libfprint's goodixmoc driver — no TOD blob needed.
  #
  # Enabling fprintd is enough for GDM: services/display-managers/gdm.nix
  # defines a `gdm-fingerprint` PAM stack whenever fprintd is on, and GDM runs
  # it in parallel with `gdm-password`, so the greeter and the GNOME lock
  # screen both accept a finger or the password. (The same module forces
  # `login.fprintAuth = false` on purpose — pam_fprintd inside `login` would
  # block the password prompt that `gdm-password` substacks.)
  #
  # sudo/polkit are pinned explicitly below. They only inherit fingerprint auth
  # from `security.pam.services.<name>.fprintAuth`, whose default happens to be
  # `services.fprintd.enable`; stating it here keeps the behaviour deliberate
  # rather than a side effect of an upstream default. Safe on this host because
  # fw16 runs no sshd, so there is no remote session for pam_fprintd to stall.
  #
  # Enrollment is per-user and inherently imperative (templates live in
  # /var/lib/fprint/<user>) — see docs/site/guides/fingerprint.md.
  services.fprintd.enable = true;
  security.pam.services.sudo.fprintAuth = true;
  security.pam.services.polkit-1.fprintAuth = true;

  # Expose Ollama to the tailnet so other devices can use it as a remote LLM
  # backend. Listening on 0.0.0.0 is safe here because the firewall only opens
  # port 11434 on the tailscale0 interface — it stays closed on Wi-Fi/ethernet.
  services.ollama.host = "0.0.0.0";
  networking.firewall.interfaces."tailscale0".allowedTCPPorts = [11434];

  networking.hostName = "fw16";

  # Set to the NixOS version used for the initial install.
  system.stateVersion = "25.05";
}

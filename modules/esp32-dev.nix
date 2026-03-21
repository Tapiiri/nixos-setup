# NixOS module: ESP32 development support
#
# Provides:
#   - nix-ld for running PlatformIO's dynamically-linked toolchains
#   - udev rules for common ESP32 USB-serial chips (CP210x, CH340/CH341)
#   - Adds configured users to the `dialout` group for serial port access
#
# Usage in host config:
#   my.esp32-dev.enable = true;
#   my.esp32-dev.users = [ "tapiiri" ];
{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf mkOption types;
  cfg = config.my.esp32-dev;
in {
  options.my.esp32-dev = {
    enable = mkEnableOption "ESP32 development support (udev + dialout)";

    users = mkOption {
      type = types.listOf types.str;
      default = [];
      description = ''
        User accounts to add to the `dialout` group so they can access
        ESP32 serial ports without root.
      '';
    };
  };

  config = mkIf cfg.enable {
    # nix-ld: provides a dynamic linker stub at /lib64/ld-linux-x86-64.so.2
    # so PlatformIO's downloaded toolchains (xtensa-esp32-elf-gcc etc.) can run.
    programs.nix-ld.enable = true;

    # udev rules for the most common ESP32 USB-to-serial bridges.
    services.udev.extraRules = ''
      # CP210x (Silicon Labs) — ESP32 DevKitC, many Espressif boards
      SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE="0666", TAG+="uaccess"

      # CH340 / CH341 — popular on budget ESP32 boards
      SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", MODE="0666", TAG+="uaccess"

      # FTDI FT232R — less common but still seen on some boards
      SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", MODE="0666", TAG+="uaccess"

      # CP2102N (newer Silicon Labs variant)
      SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea70", MODE="0666", TAG+="uaccess"

      # ESP32-S2/S3/C3 native USB (Espressif VID)
      SUBSYSTEM=="tty", ATTRS{idVendor}=="303a", MODE="0666", TAG+="uaccess"
    '';

    # Add specified users to the dialout group.
    users.groups.dialout = {};
    users.users = lib.genAttrs cfg.users (user: {
      extraGroups = ["dialout"];
    });
  };
}

# devenv.nix — ESP32 IR remote project
#
# Enter the dev shell with: devenv shell
# Then use PlatformIO: pio run, pio run -t upload, pio device monitor
{pkgs, ...}: let
  pio = pkgs.platformio-core;
in {
  dotenv.disableHint = true;

  packages = with pkgs; [
    pio
    esptool # standalone flash/debug tool
    screen # serial monitor fallback
    picocom # lightweight serial monitor alternative
    python3 # PlatformIO internals + scripting
    usbutils # lsusb — verify ESP32 detected
    git
  ];

  enterShell = ''
    echo "🔧 ESP32 IR remote devenv ready.  PlatformIO $(pio --version)"
    echo ""
    echo "Quick start:"
    echo "  pio run                  # compile"
    echo "  pio run -t upload        # flash to board"
    echo "  pio device monitor       # serial monitor (115200)"
    echo ""
    if ! groups | grep -q dialout; then
      echo "⚠  Your user is not in the 'dialout' group."
      echo "   Add my.esp32-dev.enable = true; to your NixOS config and rebuild."
    fi
  '';

  tasks = {
    "build" = {
      description = "Compile ESP32 firmware";
      exec = "pio run";
    };

    "flash" = {
      description = "Flash firmware to ESP32";
      exec = "pio run -t upload";
    };

    "monitor" = {
      description = "Open serial monitor (115200 baud)";
      exec = "pio device monitor -b 115200";
    };

    "clean" = {
      description = "Clean build artifacts";
      exec = "pio run -t clean";
    };

    "build-and-monitor" = {
      description = "Build, flash, and open serial monitor";
      exec = "pio run -t upload && pio device monitor -b 115200";
    };
  };
}

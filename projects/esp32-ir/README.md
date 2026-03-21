# ESP32 IR Remote — devenv project

Receive and retransmit infrared signals with an ESP32 DevKit.

## Prerequisites

- NixOS host has `my.esp32-dev.enable = true` (udev rules + dialout group)
- [devenv](https://devenv.sh/) installed

## Quick start

```bash
cd projects/esp32-ir
devenv shell          # enter the dev environment
pio run               # compile
pio run -t upload     # flash to board
pio device monitor    # open serial monitor (115200 baud)
```

## Wiring

| Component        | ESP32 Pin |
|------------------|-----------|
| IR receiver data | GPIO 14   |
| IR LED           | GPIO 15   |
| BOOT button      | GPIO 0    |

## Devenv tasks

```bash
devenv tasks run build             # compile
devenv tasks run flash             # flash
devenv tasks run monitor           # serial monitor
devenv tasks run build-and-monitor # flash + monitor
devenv tasks run clean             # clean build
```

## VS Code

The PlatformIO IDE extension works with this setup.  Open this folder
as a workspace (or use the repo's `scripts/code` wrapper from the
`projects/esp32-ir` directory) so PlatformIO picks up the
`platformio.ini`.

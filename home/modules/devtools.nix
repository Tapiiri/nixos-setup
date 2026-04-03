{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf mkOption types;
  # Pin Python explicitly so scripts/tests use a known interpreter.
  py = pkgs.python313;
  pyPkgs = py.pkgs;
in {
  imports = [
    ./gh.nix
  ];

  options.my.devtools = {
    enable = mkEnableOption "Developer tools (gh, vscode, language runtimes)";
    vscode.enable = mkOption {
      type = types.bool;
      default = true;
      description = "Whether devtools should also enable and configure VS Code.";
    };
  };

  config = mkIf config.my.devtools.enable {
    my.gh.enable = true;
    my.vscode.enable = config.my.devtools.vscode.enable;
    programs.vscode.enable = config.my.devtools.vscode.enable;

    # Development tooling.
    #
    # Note: We pin Python explicitly (instead of pkgs.python3) so:
    # - repo scripts run with a known interpreter version
    # - unit tests and linters come from the same interpreter set
    home.packages = with pkgs; [
      cachix
      devenv
      cloudflared
      secretspec
      nodejs_latest
      claude-code
      bottom # system monitor (btm) — per-process CPU/RAM/disk/network
      ffmpeg-full
      # Nix tooling used by VS Code (nix-ide expects these to exist).
      nil
      alejandra
      # Pinned Python + repo script tooling.
      py
      pyPkgs.ffmpeg-python
      pyPkgs.pytest
      pyPkgs.ruff
    ];
  };
}

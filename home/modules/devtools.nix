{ config
, lib
, pkgs
, ...
}:
let
  inherit (lib) mkEnableOption mkIf;
  # Pin Python explicitly so scripts/tests use a known interpreter.
  py = pkgs.python313;
  pyPkgs = py.pkgs;
in
{
  imports = [
    ./gh.nix
  ];

  options.my.devtools.enable = mkEnableOption "Developer tools (gh, vscode, language runtimes)";

  config = mkIf config.my.devtools.enable {
    my.gh.enable = true;
    my.vscode.enable = true;
    programs.vscode.enable = true;

    # Development tooling.
    #
    # Note: We pin Python explicitly (instead of pkgs.python3) so:
    # - repo scripts run with a known interpreter version
    # - unit tests and linters come from the same interpreter set
    home.packages = with pkgs; [
      nodejs_latest
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

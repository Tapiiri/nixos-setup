{ config, lib, pkgs, ... }:

let
  inherit (lib) mkEnableOption mkIf;
in
{
  options.my.devtools.enable = mkEnableOption "Developer tools (gh, vscode, language runtimes)";

  config = mkIf config.my.devtools.enable {
    programs.gh.enable = true;
    programs.vscode.enable = true;

    # Development tooling.
    home.packages = with pkgs; [
      nodejs_latest
      python3
      ffmpeg-full
      python3Packages.ffmpeg-python
    ];
  };
}

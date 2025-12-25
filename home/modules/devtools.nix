{ pkgs, ... }:

{
  programs.gh.enable = true;
  programs.vscode.enable = true;

  # Development tooling.
  home.packages = with pkgs; [
    nodejs_latest
    python3
    ffmpeg-full
    python3Packages.ffmpeg-python
  ];
}

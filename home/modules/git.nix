{ pkgs, ... }:

{
  programs.git = {
    package = pkgs.gitAndTools.gitFull;
    enable = true;
    userName = "Ilmari Tarpila";
    userEmail = "ilmari@tarpia.fi";
  };
}

{ config, lib, pkgs, ... }:

let
  inherit (lib) mkEnableOption mkIf;
in
{
  options.my.git.enable = mkEnableOption "Git (programs.git)";

  config = mkIf config.my.git.enable {
    programs.git = {
      package = pkgs.gitAndTools.gitFull;
      enable = true;
      userName = "Ilmari Tarpila";
      userEmail = "ilmari@tarpia.fi";
    };
  };
}

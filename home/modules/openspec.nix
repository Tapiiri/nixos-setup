{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.openspec.enable = mkEnableOption "OpenSpec spec-driven development CLI";

  config = mkIf config.my.openspec.enable {
    # `openspec init` / `openspec update` write per-project files under
    # openspec/, so nothing here is configured globally — the CLI just needs
    # to be on PATH outside project shells.
    home.packages = [pkgs.openspec];
  };
}

{
  config,
  lib,
  pkgs,
  flakeRoot,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.posthog-desktop.enable = mkEnableOption "PostHog Desktop (repackaged .deb)";

  config = mkIf config.my.posthog-desktop.enable {
    home.packages = [
      (pkgs.callPackage (flakeRoot + "/pkgs/apps/posthog-desktop.nix") {})
    ];
  };
}

{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.thunderbird.enable = mkEnableOption "Thunderbird email client";

  config = mkIf config.my.thunderbird.enable {
    home.packages = [pkgs.thunderbird];

    programs.thunderbird = {
      enable = true;
      profiles.default = {
        isDefault = true;
      };
    };
  };
}

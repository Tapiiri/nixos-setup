{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf mkOption types;
in {
  options.my.gh.enable = mkEnableOption "GitHub CLI (gh)";

  # Optional: set the GitHub login explicitly.
  # Note: this does NOT affect commit attribution; it's only for gh defaults.
  options.my.gh.user = mkOption {
    type = types.nullOr types.str;
    default = null;
    example = "Tapiiri";
    description = "GitHub username (login) for gh CLI settings.";
  };

  config = mkIf config.my.gh.enable {
    programs.gh = {
      enable = true;

      settings = mkIf (config.my.gh.user != null) {
        user = config.my.gh.user;
      };
    };
  };
}

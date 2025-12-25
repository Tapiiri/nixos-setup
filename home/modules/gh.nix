{ config, lib, pkgs, ... }:

let
  inherit (lib) mkEnableOption mkIf;

  # Match the GitHub CLI "user" to whatever userEmail is set in git.
  # `programs.gh.settings.user` expects your GitHub username (login), but we only
  # have a git identity here. So we derive it from the email local-part.
  #
  # If you need the exact GitHub login and it's not the same as the email
  # local-part, we can add an explicit option later.
  gitEmail = config.programs.git.userEmail or null;
  ghUser =
    if gitEmail == null then null
    else builtins.elemAt (lib.splitString "@" gitEmail) 0;

  ghUserSettings =
    if ghUser == null then { }
    else { user = ghUser; };
in
{
  options.my.gh.enable = mkEnableOption "GitHub CLI (gh)";

  config = mkIf config.my.gh.enable {
    programs.gh = {
      enable = true;

      # Keep gh's notion of "user" aligned with the configured git email.
      settings = ghUserSettings;
    };
  };
}

{
  flakeRoot,
  pkgs,
  ...
}: {
  imports = [
    (import (flakeRoot + "/home/modules/core.nix") "ilmari-offeri" {NIXOS_PROFILE = "offeri";})
    (flakeRoot + "/home/modules/default.nix")
  ];

  home.packages = with pkgs; [
    pnpm
  ];

  my = {
    git.enable = true;
    devtools = {
      enable = true;
      vscode.enable = false;
    };
    browsers.enable = true;
    shell.bash.enable = true;
    thunderbird.enable = true;
    outlookWeb.enable = true;
    teams.enable = true;
    cursor.enable = true;
    notion.enable = true;
    linear.enable = true;
    hmSwitch.enable = true;
  };

  programs.git.settings = {
    user.name = "Ilmari Tarpila";
  };

  home.sessionVariables = {
    NIXOS_SETUP_HM_PROFILE = "ilmari-offeri";
  };
}

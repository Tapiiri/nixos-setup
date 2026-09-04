{
  flakeRoot,
  pkgs,
  ...
}: {
  imports = [
    (import (flakeRoot + "/home/modules/core.nix") "ilmari-offeri" {NIXOS_PROFILE = "offeri";})
    (flakeRoot + "/home/modules/default.nix")
  ];

  # Comfort runtimes for offeriai/tarjousai (Next.js + TypeScript).
  # Project-local npm/devenv still owns the exact toolchain; these are
  # available at login for working outside `nix develop`.
  home.packages = with pkgs; [
    pnpm
  ];

  my = {
    git.enable = true;
    devtools.enable = true;
    browsers.enable = true;
    shell.bash.enable = true;
    thunderbird.enable = true;
    outlookWeb.enable = true;
    teams.enable = true;
    cursor.enable = true;
    notion.enable = true;
    linear.enable = true;
    rebuild.enable = true;
    userSwitch.enable = true;
    switchSpecialisation.enable = true;
    onepassword.enable = true;
  };

  programs.git.settings = {
    user.name = "Ilmari Tarpila";
  };
}

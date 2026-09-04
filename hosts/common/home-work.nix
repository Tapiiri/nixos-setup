{
  flakeRoot,
  pkgs,
  ...
}: {
  imports = [
    (import (flakeRoot + "/home/modules/core.nix") "ilmari" {NIXOS_PROFILE = "work";})
    (flakeRoot + "/home/modules/default.nix")
  ];

  # Comfort runtimes available at login (task runner, fuzzy finder,
  # Python package manager).
  home.packages = with pkgs; [
    just
    fzf
    uv
  ];

  my = {
    git.enable = true;
    devtools.enable = true;
    browsers.enable = true;
    shell.bash.enable = true;
    thunderbird.enable = true;
    slack.enable = true;
    rebuild.enable = true;
    userSwitch.enable = true;
    switchSpecialisation.enable = true;
    # Personal modules intentionally disabled:
    # telegram.enable = false;   (default)
    onepassword.enable = true;
    # tailscale.enable = false;  (default)
  };

  # Override git identity for work commits.
  programs.git.settings = {
    user.name = "Ilmari Tarpila";
  };
}

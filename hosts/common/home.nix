{flakeRoot, ...}: {
  my = {
    git.enable = true;
    devtools.enable = true;
    browsers.enable = true;
    shell.bash.enable = true;
    telegram.enable = true;
    slack.enable = true;
    onepassword.enable = true;
    thunderbird.enable = true;
    rebuild.enable = true;
    userSwitch.enable = true;
    switchSpecialisation.enable = true;
    zellij.enable = true;
    moonlight.enable = true;
  };

  # Home Manager module hub.
  #
  # Convention:
  # - One "program = one module" is a great default (`git.nix`, `zsh.nix`, ...)
  # - Group modules are also fine when configs are tightly related
  #   (`browsers.nix`, `devtools.nix`, `desktop-gnome.nix`, ...).
  imports = [
    (import (flakeRoot + "/home/modules/core.nix") "tapiiri" {})
    (flakeRoot + "/home/modules/default.nix")
  ];
}

{ flakeRoot, ... }:

{
  # Home Manager module hub.
  #
  # Convention:
  # - One “program = one module” is a great default (`git.nix`, `zsh.nix`, ...)
  # - Group modules are also fine when configs are tightly related
  #   (`browsers.nix`, `devtools.nix`, `desktop-gnome.nix`, ...).
  imports = [
    (flakeRoot + "/home/modules/core.nix")
    (flakeRoot + "/home/modules/git.nix")
    (flakeRoot + "/home/modules/devtools.nix")
    (flakeRoot + "/home/modules/browsers.nix")
    (flakeRoot + "/home/modules/shell-bash.nix")
  ];
}

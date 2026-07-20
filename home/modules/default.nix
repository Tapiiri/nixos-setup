{flakeRoot, ...}: {
  # Module registry.
  # Add new modules here and they become available to your Home Manager config.
  #
  # Flake note: new module files must be tracked/staged in git, otherwise they
  # won't be included in the flake source snapshot in /nix/store and imports
  # will fail during `nix flake check` / rebuild.
  imports = [
    (flakeRoot + "/home/modules/nix-caches.nix")
    (flakeRoot + "/home/modules/git.nix")
    (flakeRoot + "/home/modules/gh.nix")
    (flakeRoot + "/home/modules/devtools.nix")
    (flakeRoot + "/home/features/dokploy")
    (flakeRoot + "/home/modules/onepassword.nix")
    (flakeRoot + "/home/features/vscode")
    (flakeRoot + "/home/modules/browsers.nix")
    (flakeRoot + "/home/modules/tailscale.nix")
    (flakeRoot + "/home/modules/telegram.nix")
    (flakeRoot + "/home/modules/slack.nix")
    (flakeRoot + "/home/modules/shell-bash.nix")
    (flakeRoot + "/home/modules/thunderbird.nix")
    (flakeRoot + "/home/modules/scripts.nix")
    (flakeRoot + "/home/modules/zellij.nix")
    (flakeRoot + "/home/modules/affinity.nix")
    (flakeRoot + "/home/modules/moonlight.nix")
  ];
}

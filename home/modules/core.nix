# Parameterized core identity module.
# Usage in imports:
#   (import (flakeRoot + "/home/modules/core.nix") "tapiiri" {})
#   (import (flakeRoot + "/home/modules/core.nix") "ilmari" { NIXOS_PROFILE = "work"; })
username: extraSessionVariables: {...}: {
  home.username = username;
  home.homeDirectory = "/home/${username}";

  # Ensure scripts linked to ~/.local/bin are discoverable.
  home.sessionPath = [".local/bin"];

  # Some setups won't propagate home.sessionPath into hm-session-vars.sh
  # (it should, but this makes it unambiguous).
  home.sessionVariables =
    {
      PATH = "$HOME/.local/bin:$PATH";
    }
    // extraSessionVariables;

  # Keep this close to the root of HM config so it's easy to find.
  home.stateVersion = "25.05";

  # Let Home Manager install and manage itself.
  programs.home-manager.enable = true;
}

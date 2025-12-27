{...}: {
  # Identity / base settings.
  home.username = "tapiiri";
  home.homeDirectory = "/home/tapiiri";

  # Ensure scripts linked to ~/.local/bin are discoverable.
  home.sessionPath = [".local/bin"];

  # Some setups won't propagate home.sessionPath into hm-session-vars.sh
  # (it should, but this makes it unambiguous).
  home.sessionVariables = {
    PATH = "$HOME/.local/bin:$PATH";
  };

  # Keep this close to the root of HM config so it's easy to find.
  home.stateVersion = "25.05";

  # Let Home Manager install and manage itself.
  programs.home-manager.enable = true;

  nixpkgs.config.allowUnfree = true;
}

{...}: {
  # Identity / base settings for Catalys Engineering work account.
  home.username = "ilmari";
  home.homeDirectory = "/home/ilmari";

  home.sessionPath = [".local/bin"];

  home.sessionVariables = {
    PATH = "$HOME/.local/bin:$PATH";
    NIXOS_PROFILE = "work";
  };

  home.stateVersion = "25.05";

  programs.home-manager.enable = true;

  nixpkgs.config.allowUnfree = true;
}

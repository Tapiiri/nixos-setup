{ config, pkgs, ... }:

{
  # Home Manager needs a bit of information about you and the
  # paths it should manage.
  home.username = "tapiiri";
  home.homeDirectory = "/home/tapiiri";

  # Ensure scripts linked to ~/.local/bin are discoverable.
  home.sessionPath = [ "$HOME/.local/bin" ];

  # Some setups won't propagate home.sessionPath into hm-session-vars.sh
  # (it should, but this makes it unambiguous).
  home.sessionVariables = {
    PATH = "$HOME/.local/bin:$PATH";
  };

  programs.git = {
    package = pkgs.gitAndTools.gitFull;
    enable = true;
    userName = "Ilmari Tarpila";
    userEmail = "ilmari@tarpia.fi";
  };

  programs.gh = {
    enable = true;
  };
  
  programs.vscode = {
   enable = true;
  };

  programs.google-chrome = {
   enable = true;
  };

  programs.firefox = {
    enable = true;
  };

  # Make sure Home Manager's session variables (including home.sessionPath)
  # are actually loaded by interactive/login shells.
  programs.bash = {
    enable = true;
    profileExtra = ''
      # Load Home Manager session variables (PATH, locale, etc.)
      if [ -f "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh" ]; then
        . "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh"
      fi
    '';
  };


  # Add Node.js (latest LTS) with npm for Next.js development
  home.packages = with pkgs; [
    nodejs_latest
    ffmpeg-full
    python3
    python3Packages.ffmpeg-python
  ];


  # This value determines the Home Manager release that your
  # configuration is compatible with. This helps avoid breakage
  # when a new Home Manager release introduces backwards
  # incompatible changes.
  #
  # You can update Home Manager without changing this value. See
  # the Home Manager release notes for a list of state version
  # changes in each release.
  home.stateVersion = "25.05";

  # Let Home Manager install and manage itself.
  programs.home-manager.enable = true;

  nixpkgs.config.allowUnfree = true;
}

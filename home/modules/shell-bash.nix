{ ... }:

{
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
}

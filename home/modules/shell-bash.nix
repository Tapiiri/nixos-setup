{ config, lib, ... }:

let
  inherit (lib) mkEnableOption mkIf;
in
{
  options.my.shell.bash.enable = mkEnableOption "Bash config";

  config = mkIf config.my.shell.bash.enable {
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

      # Many terminals (including VS Code's integrated terminal) start an
      # interactive *non-login* shell by default, which won't read
      # ~/.bash_profile or profileExtra.
      #
      # Sourcing hm-session-vars.sh here makes `home.sessionPath` (e.g.
      # ~/.local/bin) reliably available.
      bashrcExtra = ''
        if [ -f "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh" ]; then
          . "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh"
        fi
      '';
    };
  };
}

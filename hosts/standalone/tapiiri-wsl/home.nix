{
  pkgs,
  flakeRoot,
  ...
}: {
  imports = [
    (flakeRoot + "/home/modules/core.nix")
    (flakeRoot + "/home/modules/scripts.nix")
  ];

  my.hmSwitch.enable = true;

  home.packages = [
    pkgs.claude-code
    pkgs.cloudflared
  ];

  home.sessionVariables = {
    NIXOS_SETUP_HM_PROFILE = "tapiiri-wsl";
  };

  # Ensure home.sessionVariables are loaded in every shell.
  programs.bash = {
    enable = true;
    profileExtra = ''
      if [ -f "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh" ]; then
        . "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh"
      fi
    '';
    bashrcExtra = ''
      if [ -f "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh" ]; then
        . "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh"
      fi
    '';
  };
}

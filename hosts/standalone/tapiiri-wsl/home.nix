{
  pkgs,
  lib,
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

  # Idempotently patch existing shell rc files to source HM session vars,
  # without clobbering Ubuntu's default .bashrc / .profile.
  home.activation.sourceHmSessionVars = lib.hm.dag.entryAfter ["writeBoundary"] ''
    _marker="# Source Home Manager session variables"
    _snippet="$_marker
    if [ -f \"\$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh\" ]; then
      . \"\$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh\"
    fi"

    for _f in "$HOME/.bashrc" "$HOME/.profile"; do
      if [ -f "$_f" ] && ! grep -qF "$_marker" "$_f"; then
        printf '\n%s\n' "$_snippet" >> "$_f"
      fi
    done
  '';
}

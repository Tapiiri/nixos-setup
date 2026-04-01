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
}

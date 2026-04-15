{flakeRoot, ...}: {
  imports = [
    (flakeRoot + "/home/modules/core-work.nix")
    (flakeRoot + "/home/modules/default.nix")
  ];

  my = {
    git.enable = true;
    devtools = {
      enable = true;
      vscode.enable = false;
    };
    shell.bash.enable = true;
    hmSwitch.enable = true;
  };

  home.sessionVariables = {
    NIXOS_SETUP_HM_PROFILE = "ilmari";
  };
}

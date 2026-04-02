{flakeRoot, ...}: {
  imports = [
    (flakeRoot + "/home/modules/core-work.nix")
    (flakeRoot + "/home/modules/default.nix")
  ];

  my = {
    git.enable = true;
    devtools.enable = true;
    dokployCli.enable = true;
    browsers.enable = true;
    shell.bash.enable = true;
    thunderbird.enable = true;
    userSwitch.enable = true;
    # Personal modules intentionally disabled:
    # telegram.enable = false;   (default)
    onepassword.enable = true;
    # tailscale.enable = false;  (default)
  };

  # Override git identity for work commits.
  programs.git.settings = {
    user.name = "Ilmari Tarpila";
    user.email = "ilmari@catalys-engineering.com";
  };
}

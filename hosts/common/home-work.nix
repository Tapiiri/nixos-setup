{
  flakeRoot,
  pkgs,
  ...
}: {
  imports = [
    (flakeRoot + "/home/modules/core-work.nix")
    (flakeRoot + "/home/modules/default.nix")
  ];

  # Comfort runtimes available at login — mirrors the subset of vaisala-pilot's
  # devenv that is useful outside `nix develop` (task runner, fuzzy finder,
  # Python package manager for nwave). Services (PostgreSQL, Caddy) are managed
  # by systemd via infra/nixos/modules/local-dev.nix; runtimes provided by
  # devtools.nix (node, python, etc.) are already covered.
  home.packages = with pkgs; [
    just
    fzf
    uv
  ];

  my = {
    git.enable = true;
    devtools.enable = true;
    browsers.enable = true;
    shell.bash.enable = true;
    thunderbird.enable = true;
    slack.enable = true;
    rebuild.enable = true;
    userSwitch.enable = true;
    switchSpecialisation.enable = true;
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

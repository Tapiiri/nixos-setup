{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf mkOption types;
in {
  options.my.git.enable = mkEnableOption "Git (programs.git)";

  options.my.git.signing = {
    enable = mkEnableOption "Git commit/tag signing (SSH via gpg.format=ssh)";

    # If set, should point to the *public* key file used for SSH signing.
    # Example: ~/.ssh/id_ed25519_git_signing.pub
    key = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "Path to SSH signing public key for Git (user.signingKey).";
      example = "~/.ssh/id_ed25519_git_signing.pub";
    };
  };

  config = mkIf config.my.git.enable {
    programs.git = {
      package = pkgs.gitAndTools.gitFull;
      enable = true;
      userName = "Tapiiri";
      userEmail = "ilmari@tarpia.fi";

      # GitHub shows your avatar / marks commits as yours when the commit email
      # matches an email verified on your GitHub account. Keep this aligned.

      extraConfig = {
        init.defaultBranch = "main";

        # Git 2.27+ requires configuring how `git pull` reconciles divergent
        # branches. We prefer the traditional merge strategy by default.
        pull.rebase = false;

    # Optional signing setup.
    #
    # NOTE: We prefer using Home Manager's `programs.git.signing.*` options
    # (below) to turn signing on/off. These extraConfig values only specify
    # the signing mechanism when signing is enabled.
    gpg.format = mkIf config.my.git.signing.enable "ssh";

        safe.directory = [
          "/etc/nixos"
        ];
      };

      # Home Manager's stable way to configure commit signing.
      signing = mkIf config.my.git.signing.enable {
        signByDefault = true;
        key = mkIf (config.my.git.signing.key != null) config.my.git.signing.key;
      };
    };
  };
}

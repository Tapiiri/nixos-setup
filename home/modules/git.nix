{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.git.enable = mkEnableOption "Git (programs.git)";

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

        # Make it easier to get GitHub's green "Verified" badge by signing.
        # Preferred modern setup is SSH signing:
        #   - create a signing key: ssh-keygen -t ed25519 -C "git-signing"
        #   - add the *public* key to GitHub: Settings -> SSH and GPG keys ->
        #     "New SSH key" -> Key type: "Signing key"
        #   - set user.signingKey to the public key file path.
        gpg.format = "ssh";
        commit.gpgSign = true;
        tag.gpgSign = true;

        safe.directory = [
          "/etc/nixos"
        ];
      };
    };
  };
}

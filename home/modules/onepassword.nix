{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf mkOption types;

  # Package names differ slightly across nixpkgs versions; in 25.05 these
  # should exist as unfree packages when `allowUnfree = true`.
  onepasswordPkg = pkgs._1password-gui;
  onepasswordCLIPkg = pkgs._1password-cli;

  mkPkgOption = pkg:
    mkOption {
      type = types.package;
      default = pkg;
      defaultText = "pkgs.${pkg.pname or "<package>"}";
      description = "Package to install.";
    };
in {
  options.my.onepassword = {
    enable = mkEnableOption "1Password (GUI + CLI)";

    installGui = mkOption {
      type = types.bool;
      default = true;
      description = "Install the 1Password desktop app.";
    };

    installCli = mkOption {
      type = types.bool;
      default = true;
      description = "Install the 1Password CLI (op).";
    };

    onepasswordPkg.polkitPolicyOwners = ["tapiiri"];

    guiPackage = mkPkgOption onepasswordPkg;
    cliPackage = mkPkgOption onepasswordCLIPkg;
  };

  config = mkIf config.my.onepassword.enable {
    home.packages =
      (lib.optional config.my.onepassword.installGui config.my.onepassword.guiPackage)
      ++ (lib.optional config.my.onepassword.installCli config.my.onepassword.cliPackage);
  };
}

# Home Manager companion for 1Password.
#
# The actual packages and permissions are handled by the NixOS system modules
# (programs._1password and programs._1password-gui in configuration.nix).
# This module exists so that `my.onepassword.enable = true` still works as a
# feature flag in Home Manager configs — it's just a no-op now since the system
# modules provide the binaries with proper suid/group permissions.
{lib, ...}: let
  inherit (lib) mkEnableOption;
in {
  options.my.onepassword = {
    enable = mkEnableOption "1Password (GUI + CLI)";
  };

  # No home.packages — the NixOS system modules install the binaries with the
  # required suid wrappers and onepassword-cli group ownership.
}

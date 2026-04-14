# Declaratively manage user-level Cachix binary caches via Home Manager.
#
# This writes ~/.config/nix/nix.conf with the correct substituters,
# preventing stale entries from accumulating (as happens with imperative
# `cachix use` commands).  Uses extra-* settings so they layer on top of
# any system-level config without overriding it.
{
  lib,
  cachixCaches,
  ...
}: let
  allCaches = builtins.attrValues cachixCaches;
  urls = lib.concatStringsSep " " (map (c: c.url) allCaches);
  keys = lib.concatStringsSep " " (map (c: c.publicKey) allCaches);
in {
  xdg.configFile."nix/nix.conf" = {
    text = ''
      # Managed by Home Manager — do not edit manually.
      # Source of truth: cachix-caches.nix in the nixos-setup repo.
      experimental-features = nix-command flakes
      extra-substituters = ${urls}
      extra-trusted-public-keys = ${keys}
    '';
    force = true;
  };
}

# Single source of truth for Cachix binary cache configuration.
#
# Referenced by:
#   - flake.nix          → NixOS system-level nix.settings (via specialArgs)
#   - devenv.nix         → cachix.pull for the devenv cache
#   - home/modules/nix-caches.nix → user-level ~/.config/nix/nix.conf (via HM)
#
# When renaming a cache, update the name/url/publicKey here and all consumers
# pick up the change automatically.  Home Manager will rewrite the user-level
# nix.conf on next activation, removing stale entries.
{
  nixos = {
    name = "tapiiri-nixos-setup";
    url = "https://tapiiri-nixos-setup.cachix.org";
    publicKey = "tapiiri-nixos-setup.cachix.org-1:wBjh1nFp9lCRgdt6eOMPEv14KIE51cjYW0VczdgKYEU=";
  };
  devenv = {
    name = "tapiiri-nixos-setup-devenv";
    url = "https://tapiiri-nixos-setup-devenv.cachix.org";
    publicKey = "tapiiri-nixos-setup-devenv.cachix.org-1:1OFdW8dY+TOwBfCXvSnAOFcwLpvvqNzjfp07K655rDk=";
  };
  # Official devenv binary cache — provides pre-built packages from
  # devenv-nixpkgs/rolling (used as nixpkgs input in devenv.yaml).
  # Without this, packages like pre-commit fall back to building from source.
  devenvOfficial = {
    name = "devenv";
    url = "https://devenv.cachix.org";
    publicKey = "devenv.cachix.org-1:w1cLUi8dv3hnoSPGAuibQv+f9TZLr6cv/Hm9XgU50cw=";
  };
  # nix-community cache — provides pre-built packages for community flakes
  # such as lanzaboote (Secure Boot) and home-manager tools.
  nixCommunity = {
    name = "nix-community";
    url = "https://nix-community.cachix.org";
    publicKey = "nix-community.cachix.org-1:mB9FSh9qf2dCimDSUo8Zy7bkq5CX+/rkCWyvRCUSeBc=";
  };
  # Garnix CI cache — provides pre-built binaries for flakes built by Garnix CI,
  # including affinity-nix (Affinity v3 via Wine).
  garnix = {
    name = "garnix";
    url = "https://cache.garnix.io";
    publicKey = "cache.garnix.io:CTFPyKSLcx5RMJKfLo5EEPUObbA78b0YQ2DTCJXqr9g=";
  };
}

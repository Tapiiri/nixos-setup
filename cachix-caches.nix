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
}

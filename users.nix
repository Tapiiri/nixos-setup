# User registry — single source of truth for all user identities.
# To add a new user:
#   1. Add an entry here
#   2. Create hosts/common/home-<name>.nix (and optionally hosts/standalone/<name>/home.nix)
#   3. Optionally add to host specialisation `users` lists
{
  tapiiri = {
    description = "Ilmari Tarpila";
    extraGroups = ["networkmanager" "wheel" "nixos-setup"];
    isTrusted = true;
    sessionVariables = {};
    nixosHome = ./hosts/common/home.nix;
    standalone = {
      tapiiri = {
        system = "x86_64-linux";
        module = ./hosts/standalone/tapiiri/home.nix;
      };
      tapiiri-wsl = {
        system = "x86_64-linux";
        module = ./hosts/standalone/tapiiri-wsl/home.nix;
      };
    };
  };

  ilmari = {
    description = "Ilmari (work)";
    extraGroups = ["networkmanager"];
    isTrusted = true;
    sessionVariables = {NIXOS_PROFILE = "work";};
    nixosHome = ./hosts/common/home-work.nix;
    claudeSeedFrom = "tapiiri";
    standalone = {
      ilmari = {
        system = "x86_64-linux";
        module = ./hosts/standalone/ilmari/home.nix;
      };
    };
  };
}

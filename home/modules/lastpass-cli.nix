{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.lastpass-cli.enable = mkEnableOption "Lastpass password manager CLI";

  config = mkIf config.my.lastpass-cli.enable (let
    patchedLastpass = pkgs.lastpass-cli.overrideAttrs (old: {
      # Preserve any existing postPatch and append our sed tweak.
      postPatch =
        (old.postPatch or "")
        + ''
          # Normalize CMake minimum version to avoid compatibility removal in newer CMake
          if [ -f CMakeLists.txt ]; then
            sed -i 's/cmake_minimum_required(VERSION 2.8)/cmake_minimum_required(VERSION 3.5)/' CMakeLists.txt || true
            sed -i 's/cmake_minimum_required(VERSION 3.1)/cmake_minimum_required(VERSION 3.5)/' CMakeLists.txt || true
          fi
        '';
      # Ensure the cmake invocation receives the policy minimum as a fallback
      cmakeFlags = (old.cmakeFlags or []) ++ ["-DCMAKE_POLICY_VERSION_MINIMUM=3.5"];
    });
  in {
    home.packages = [patchedLastpass];
  });
}

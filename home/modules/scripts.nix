# Auto-generated Home Manager options for flake script packages.
#
# To make a new script installable via Home Manager:
#   1. Add a flake package in flake.nix (scriptSpecs table)
#   2. Add a matching entry to scriptPackages below
#
# Each entry maps a flake package name to an HM option path so users can write:
#   my.userSwitch.enable = true;
# and the corresponding package is added to home.packages automatically.
{
  config,
  lib,
  pkgs,
  flakeRoot,
  ...
}: let
  inherit (lib) mkEnableOption mkIf mkMerge mapAttrsToList setAttrByPath getAttrFromPath foldl' recursiveUpdate;

  # Maps flake package name → HM option path + description.
  scriptPackages = {
    "hm-switch" = {
      optionPath = ["my" "hmSwitch" "enable"];
      description = "Standalone Home Manager switch command (hm-switch)";
    };
    "setup-wsl-ssh" = {
      optionPath = ["my" "setupWslSsh" "enable"];
      description = "Ubuntu WSL OpenSSH setup helper (setup-wsl-ssh)";
    };
    "setup-wsl-nix" = {
      optionPath = ["my" "setupWslNix" "enable"];
      description = "Ubuntu WSL Nix daemon setup helper (setup-wsl-nix)";
    };
    "switch-user" = {
      optionPath = ["my" "userSwitch" "enable"];
      description = "User switch command (switch-user)";
    };
    "switch-specialisation" = {
      optionPath = ["my" "switchSpecialisation" "enable"];
      description = "NixOS specialisation switcher (switch-specialisation)";
    };
    # To add a new script, just add an entry here. For example:
    # rebuild = {
    #   optionPath = ["my" "rebuild" "enable"];
    #   description = "NixOS rebuild helper";
    # };
  };

  scriptOptions = foldl' recursiveUpdate {} (
    mapAttrsToList (
      _name: spec:
        setAttrByPath spec.optionPath (mkEnableOption spec.description)
    )
    scriptPackages
  );

  scriptConfigs = mkMerge (
    mapAttrsToList (
      name: spec:
        mkIf (getAttrFromPath spec.optionPath config) {
          home.packages = [
            flakeRoot.packages.${pkgs.stdenv.hostPlatform.system}.${name}
          ];
        }
    )
    scriptPackages
  );

  switchSpecialisationCompletion = ''
    _switch_specialisation_complete() {
      local cur="''${COMP_WORDS[COMP_CWORD]}"
      local spec_dir="/run/current-system/specialisation"
      local names=""
      if [[ -d "$spec_dir" ]]; then
        names=$(ls "$spec_dir" 2>/dev/null | tr '\n' ' ')
      fi
      # shellcheck disable=SC2207
      COMPREPLY=($(compgen -W "base $names --list" -- "$cur"))
    }
    complete -F _switch_specialisation_complete switch-specialisation
  '';
in {
  options = scriptOptions;
  config = mkMerge [
    scriptConfigs
    (mkIf config.my.switchSpecialisation.enable {
      programs.bash.initExtra = switchSpecialisationCompletion;
    })
  ];
}

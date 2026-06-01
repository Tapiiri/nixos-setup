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
    "rebuild" = {
      optionPath = ["my" "rebuild" "enable"];
      description = "NixOS rebuild dispatcher (rebuild)";
    };
    "switch-user" = {
      optionPath = ["my" "userSwitch" "enable"];
      description = "User switch command (switch-user)";
    };
    "switch-specialisation" = {
      optionPath = ["my" "switchSpecialisation" "enable"];
      description = "NixOS specialisation switcher (switch-specialisation)";
    };
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

  rebuildCompletion = ''
    _rebuild_complete() {
      local cur="''${COMP_WORDS[COMP_CWORD]}"
      local hosts=""
      if [[ -d /etc/nixos/hosts ]]; then
        hosts=$(ls /etc/nixos/hosts/ 2>/dev/null \
          | grep -Ev '^(base|common|installer|standalone)$' \
          | tr '\n' ' ')
      fi
      # shellcheck disable=SC2207
      COMPREPLY=($(compgen -W "$hosts --dev --offline-ok" -- "$cur"))
    }
    complete -F _rebuild_complete rebuild
  '';

  switchUserCompletion = ''
    _switch_user_complete() {
      local cur="''${COMP_WORDS[COMP_CWORD]}"
      # shellcheck disable=SC2207
      COMPREPLY=($(compgen -W "$(ls /home/ 2>/dev/null | tr '\n' ' ')" -- "$cur"))
    }
    complete -F _switch_user_complete switch-user
  '';

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
    (mkIf config.my.rebuild.enable {
      programs.bash.initExtra = rebuildCompletion;
    })
    (mkIf config.my.userSwitch.enable {
      programs.bash.initExtra = switchUserCompletion;
    })
    (mkIf config.my.switchSpecialisation.enable {
      programs.bash.initExtra = switchSpecialisationCompletion;
    })
  ];
}

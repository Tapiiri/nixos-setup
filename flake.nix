{
  description = "Nixos config flake";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = {
    self,
    nixpkgs,
    ...
  } @ inputs: let
    lib = nixpkgs.lib;
    systems = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    forAllSystems = f: lib.genAttrs systems (system: f system);
  in {
    # use "nixos", or your hostname as the name of the configuration
    # it's a better practice than "default" shown in the video
    nixosConfigurations.nixos = nixpkgs.lib.nixosSystem {
      specialArgs = {inherit inputs;};
      modules = [
        ./modules/tailscale.nix
        ./modules/rebuild.nix
        ./modules/esp32-dev.nix
        ./hosts/nixos/configuration.nix
        inputs.home-manager.nixosModules.default
      ];
    };

    packages = forAllSystems (system: let
      pkgs = import nixpkgs {inherit system;};

      sourceInfo = self.sourceInfo or {};
      upstreamDefault =
        if (sourceInfo ? owner) && (sourceInfo ? repo)
        then "git@github.com:${sourceInfo.owner}/${sourceInfo.repo}.git"
        else null;
      wrapperExtraArgs =
        lib.optionalString (upstreamDefault != null)
        " --set-default NIXOS_SETUP_REBUILD_UPSTREAM_URL ${lib.escapeShellArg upstreamDefault}";

      nixosRebuildPkg =
        if builtins.hasAttr "nixos-rebuild" pkgs
        then pkgs."nixos-rebuild"
        else if builtins.hasAttr "nixos-rebuild-ng" pkgs
        then pkgs."nixos-rebuild-ng"
        else null;

      runtimeInputs =
        [
          pkgs.git
        ]
        ++ lib.optional (nixosRebuildPkg != null) nixosRebuildPkg;

      # ── Script package specifications ──────────────────────────────
      # Each entry defines a user-facing script to package.
      # To add a new script:
      #   1. Add an entry here (packages it as a Nix derivation)
      #   2. Add a matching entry in home/modules/scripts.nix (HM option)
      scriptSpecs = {
        rebuild = {
          pname = "nixos-setup-rebuild";
          description = "nixos-setup rebuild helper";
          scripts = ["rebuild" "rebuild-inner"];
          runtimeDeps = runtimeInputs;
          wrapperArgs = wrapperExtraArgs;
          extraSrc = ["flake.nix"];
          mainProgram = "rebuild";
        };
        "switch-user" = {
          pname = "nixos-setup-switch-user";
          description = "nixos-setup user switch helper (GDM session switcher)";
          scripts = ["switch-user"];
          runtimeDeps = [pkgs.systemd];
          wrapperArgs = "";
          extraSrc = [];
          mainProgram = "switch-user";
        };
      };

      mkScriptPackage = _name: spec:
        pkgs.stdenvNoCC.mkDerivation {
          inherit (spec) pname;
          version = "0.1.0";
          src = ./.;

          nativeBuildInputs = [pkgs.makeWrapper];

          installPhase = let
            copySrc =
              lib.concatMapStringsSep "\n" (
                f: ''cp -R "${f}" "$out/share/nixos-setup/"''
              )
              spec.extraSrc;
            installScripts =
              lib.concatMapStringsSep "\n" (s: ''
                chmod +x "$out/share/nixos-setup/scripts/${s}"
                makeWrapper "${pkgs.python3}/bin/python3" "$out/bin/${s}" \
                  --add-flags "$out/share/nixos-setup/scripts/${s}" \
                  --prefix PATH : "${lib.makeBinPath spec.runtimeDeps}"${spec.wrapperArgs}
              '')
              spec.scripts;
          in ''
            runHook preInstall
            mkdir -p "$out/share/nixos-setup"
            cp -R scripts scripts_py "$out/share/nixos-setup/"
            ${copySrc}
            mkdir -p "$out/bin"
            ${installScripts}
            runHook postInstall
          '';

          meta = {
            inherit (spec) mainProgram description;
            platforms = lib.platforms.linux;
          };
        };

      scriptPackages = lib.mapAttrs mkScriptPackage scriptSpecs;
    in
      scriptPackages // {default = scriptPackages.rebuild;});

    apps = forAllSystems (system: {
      rebuild = {
        type = "app";
        program = "${self.packages.${system}.rebuild}/bin/rebuild";
      };
      "rebuild-inner" = {
        type = "app";
        program = "${self.packages.${system}.rebuild}/bin/rebuild-inner";
      };
      default = self.apps.${system}.rebuild;
    });
  };
}

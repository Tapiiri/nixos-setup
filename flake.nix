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

      rebuildPkg = pkgs.stdenvNoCC.mkDerivation {
        pname = "nixos-setup-rebuild";
        version = "0.1.0";
        src = ./.;

        nativeBuildInputs = [
          pkgs.makeWrapper
        ];

        installPhase = ''
          runHook preInstall

          mkdir -p "$out/share/nixos-setup"
          cp -R scripts scripts_py flake.nix "$out/share/nixos-setup/"

          chmod +x "$out/share/nixos-setup/scripts/rebuild"
          chmod +x "$out/share/nixos-setup/scripts/rebuild-inner"

          mkdir -p "$out/bin"
          makeWrapper "${pkgs.python3}/bin/python3" "$out/bin/rebuild" \
            --add-flags "$out/share/nixos-setup/scripts/rebuild" \
            --prefix PATH : "${lib.makeBinPath runtimeInputs}"${wrapperExtraArgs}

          makeWrapper "${pkgs.python3}/bin/python3" "$out/bin/rebuild-inner" \
            --add-flags "$out/share/nixos-setup/scripts/rebuild-inner" \
            --prefix PATH : "${lib.makeBinPath runtimeInputs}"${wrapperExtraArgs}

          runHook postInstall
        '';

        meta = {
          mainProgram = "rebuild";
          description = "nixos-setup rebuild helper";
          platforms = lib.platforms.linux;
        };
      };

      switchUserPkg = pkgs.stdenvNoCC.mkDerivation {
        pname = "nixos-setup-switch-user";
        version = "0.1.0";
        src = ./.;

        nativeBuildInputs = [
          pkgs.makeWrapper
        ];

        installPhase = ''
          runHook preInstall

          mkdir -p "$out/share/nixos-setup"
          cp -R scripts scripts_py "$out/share/nixos-setup/"

          chmod +x "$out/share/nixos-setup/scripts/switch-user"

          mkdir -p "$out/bin"
          makeWrapper "${pkgs.python3}/bin/python3" "$out/bin/switch-user" \
            --add-flags "$out/share/nixos-setup/scripts/switch-user" \
            --prefix PATH : "${lib.makeBinPath [pkgs.systemd]}"

          runHook postInstall
        '';

        meta = {
          mainProgram = "switch-user";
          description = "nixos-setup user switch helper (GDM session switcher)";
          platforms = lib.platforms.linux;
        };
      };
    in {
      rebuild = rebuildPkg;
      "switch-user" = switchUserPkg;
      default = rebuildPkg;
    });

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

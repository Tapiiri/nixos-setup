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
        ./hosts/nixos/configuration.nix
        inputs.home-manager.nixosModules.default
      ];
    };

    packages = forAllSystems (system: let
      pkgs = import nixpkgs {inherit system;};

      nixosRebuildPkg =
        if builtins.hasAttr "nixos-rebuild" pkgs
        then pkgs."nixos-rebuild"
        else if builtins.hasAttr "nixos-rebuild-ng" pkgs
        then pkgs."nixos-rebuild-ng"
        else null;

      runtimeInputs =
        [
          pkgs.git
          pkgs.sudo
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

          mkdir -p "$out/bin"
          makeWrapper "${pkgs.python3}/bin/python3" "$out/bin/rebuild" \
            --add-flags "$out/share/nixos-setup/scripts/rebuild" \
            --prefix PATH : "${lib.makeBinPath runtimeInputs}"

          runHook postInstall
        '';

        meta = {
          mainProgram = "rebuild";
          description = "nixos-setup rebuild helper";
          platforms = lib.platforms.linux;
        };
      };
    in {
      rebuild = rebuildPkg;
      default = rebuildPkg;
    });

    apps = forAllSystems (system: {
      rebuild = {
        type = "app";
        program = "${self.packages.${system}.rebuild}/bin/rebuild";
      };
      default = self.apps.${system}.rebuild;
    });
  };
}

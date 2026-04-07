{
  description = "Nixos config flake";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    nix-dokploy = {
      url = "github:el-kurto/nix-dokploy";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    affinity-nix.url = "github:mrshmllow/affinity-nix";
  };

  outputs = {
    self,
    nixpkgs,
    ...
  } @ inputs: let
    lib = nixpkgs.lib;

    # ── Repo identity (fork-friendly: change this one line) ────────
    githubOwnerRepo = "Tapiiri/nixos-setup";

    # ── Cachix binary caches (single source of truth) ────────────
    cachixCaches = import ./cachix-caches.nix;

    mkPkgs = system:
      import nixpkgs {
        inherit system;
        config.allowUnfree = true;
      };
    mkHomeConfiguration = {
      system,
      module,
    }:
      inputs.home-manager.lib.homeManagerConfiguration {
        pkgs = mkPkgs system;
        extraSpecialArgs = {
          inherit inputs cachixCaches;
          flakeRoot = self;
        };
        modules = [module];
      };
    systems = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    forAllSystems = f: lib.genAttrs systems (system: f system);
  in {
    # use "nixos", or your hostname as the name of the configuration
    # it's a better practice than "default" shown in the video
    nixosConfigurations.nixos = nixpkgs.lib.nixosSystem {
      specialArgs = {inherit inputs cachixCaches;};
      modules = [
        inputs.nix-dokploy.nixosModules.default
        ./modules/dokploy.nix
        ./modules/tailscale.nix
        ./modules/rebuild.nix
        ./modules/esp32-dev.nix
        ./hosts/nixos/configuration.nix
        inputs.home-manager.nixosModules.default
      ];
    };

    homeConfigurations = {
      tapiiri = mkHomeConfiguration {
        system = "x86_64-linux";
        module = ./hosts/standalone/tapiiri/home.nix;
      };
      "tapiiri-wsl" = mkHomeConfiguration {
        system = "x86_64-linux";
        module = ./hosts/standalone/tapiiri-wsl/home.nix;
      };
      ilmari = mkHomeConfiguration {
        system = "x86_64-linux";
        module = ./hosts/standalone/ilmari/home.nix;
      };
    };

    packages = forAllSystems (system: let
      pkgs = mkPkgs system;
      hmPkg = inputs.home-manager.packages.${system}.home-manager;

      upstreamDefault = "git@github.com:${githubOwnerRepo}.git";
      flakeUri = "github:${githubOwnerRepo}";
      wrapperExtraArgs = " --set-default NIXOS_SETUP_REBUILD_UPSTREAM_URL ${lib.escapeShellArg upstreamDefault}";

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
        "hm-switch" = {
          pname = "nixos-setup-hm-switch";
          description = "nixos-setup standalone Home Manager switch helper";
          scripts = ["hm-switch"];
          runtimeDeps = [
            pkgs.git
            hmPkg
          ];
          wrapperArgs = " --set-default NIXOS_SETUP_FLAKE_URI ${lib.escapeShellArg flakeUri}";
          extraSrc = [];
          mainProgram = "hm-switch";
        };
        "setup-wsl-ssh" = {
          pname = "nixos-setup-setup-wsl-ssh";
          description = "Ubuntu WSL OpenSSH setup helper for Tailscale deploy access";
          scripts = ["setup-wsl-ssh"];
          runtimeDeps = [];
          wrapperArgs = "";
          extraSrc = [];
          mainProgram = "setup-wsl-ssh";
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
            installBase = "$out/share/nixos-setup/${spec.mainProgram}";
            copySrc =
              lib.concatMapStringsSep "\n" (
                f: ''cp -R "${f}" "${installBase}/"''
              )
              spec.extraSrc;
            copyScripts =
              lib.concatMapStringsSep "\n" (s: ''cp "scripts/${s}" "${installBase}/scripts/${s}"'')
              spec.scripts;
            installScripts =
              lib.concatMapStringsSep "\n" (s: ''
                chmod +x "${installBase}/scripts/${s}"
                makeWrapper "${pkgs.python3}/bin/python3" "$out/bin/${s}" \
                  --add-flags "${installBase}/scripts/${s}" \
                  --prefix PATH : "${lib.makeBinPath spec.runtimeDeps}"${spec.wrapperArgs}
              '')
              spec.scripts;
          in ''
            runHook preInstall
            mkdir -p "${installBase}/scripts"
            cp -R scripts_py "${installBase}/"
            ${copyScripts}
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
      "hm-switch" = {
        type = "app";
        program = "${self.packages.${system}.hm-switch}/bin/hm-switch";
      };
      "rebuild-inner" = {
        type = "app";
        program = "${self.packages.${system}.rebuild}/bin/rebuild-inner";
      };
      default = self.apps.${system}.rebuild;
    });
  };
}

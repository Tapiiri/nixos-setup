{
  description = "Dev-only tooling for nixos-setup (tests, lint, etc.)";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
      py = pkgs.python313;
      pyEnv = py.withPackages (ps: with ps; [ pytest ruff ]);
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        packages = [
          pkgs.pre-commit
          pkgs.nixpkgs-fmt
          pkgs.yamllint
          pkgs.actionlint
          pyEnv
        ];
        shellHook = ''
          if [ -d .git ]; then
            if [ ! -x .git/hooks/pre-commit ]; then
              echo "Installing pre-commit hook (via dev shell) ..."
              pre-commit install --install-hooks >/dev/null
            fi
          fi
        '';
      };
    };
}

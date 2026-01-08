{pkgs, ...}: {
  # Keep devenv usable even when the user is not a trusted Nix user.
  # (Otherwise devenv tries to auto-manage Cachix config and can fail.)
  cachix.enable = false;
  # cachix.pull = ["mycache"];
  # cachix.push = "mycache";

  packages = with pkgs; [
    git
    pre-commit
    alejandra
    yamllint
    actionlint
    markdownlint-cli2
    shellcheck

    # Python tooling pinned together (works even without devenv python module).
    (python313.withPackages (ps:
      with ps; [
        pytest
        ruff
        tomlkit
      ]))
  ];

  # Keep pre-commit as the runner (instead of the default prek).
  git-hooks.package = pkgs.pre-commit; # see devenv 1.11 changelog
  git-hooks.hooks = {
    nix-flake-check = {
      enable = true;
      name = "nix flake check";
      entry = "devenv tasks run check:nix:flake";
      language = "system";
      files = "(\\.nix$|^flake\\.nix$|^flake\\.lock$)";
      pass_filenames = false;
    };

    alejandra-fmt = {
      enable = true;
      name = "alejandra (nix fmt)";
      entry = "devenv tasks run fmt:nix:alejandra";
      language = "system";
      files = "(^flake\\.nix$|^(hosts|home|dev)/.*\\.nix$|.*\\.nix)";
      pass_filenames = false;
    };

    yamllint = {
      enable = true;
      name = "yamllint";
      entry = "devenv tasks run lint:yaml:yamllint";
      language = "system";
      files = ".*\\.ya?ml$";
      pass_filenames = false;
    };

    actionlint = {
      enable = true;
      name = "actionlint";
      entry = "devenv tasks run lint:gha:actionlint";
      language = "system";
      files = "^\\.github/workflows/.*\\.ya?ml$";
      pass_filenames = false;
    };

    shellcheck = {
      enable = true;
      name = "shellcheck";
      entry = "devenv tasks run lint:shell:shellcheck";
      language = "system";
      files = "(.*\\.sh$|^dotfiles/home/bashrc$|^home/.*\\.sh\\.tpl$)";
      pass_filenames = false;
    };

    markdownlint = {
      enable = true;
      name = "markdownlint";
      entry = "devenv tasks run lint:md:markdownlint";
      language = "system";
      files = ".*\\.md$";
      pass_filenames = false;
    };

    ruff-check = {
      enable = true;
      name = "ruff check";
      entry = "devenv tasks run lint:python:ruff";
      language = "system";
      pass_filenames = false;
    };

    python-pytest = {
      enable = true;
      name = "pytest";
      entry = "devenv tasks run tests:python:pytest";
      language = "system";
      pass_filenames = false;
    };
  };

  # Canonical automation entrypoints.
  #
  # Conventions:
  # - Tasks are namespaced (e.g. "lint:python:ruff") so they compose well.
  # - pre-commit hooks should delegate to these tasks to avoid duplicating logic.
  tasks = {
    # --- Nix ---
    "check:nix:flake" = {
      description = "nix flake check --no-build";
      exec = "nix flake check --no-build";
    };

    "fmt:nix:alejandra" = {
      description = "Format Nix files with alejandra";
      exec = "alejandra .";
    };

    # --- YAML / GitHub Actions ---
    "lint:yaml:yamllint" = {
      description = "Lint YAML files with yamllint";
      exec = "yamllint .";
    };

    "lint:gha:actionlint" = {
      description = "Lint GitHub Actions workflows with actionlint";
      exec = "actionlint";
    };

    # --- Shell / templates ---
    "lint:shell:shellcheck" = {
      description = "Lint shell scripts with shellcheck";
      exec = "shellcheck $(git ls-files '*.sh' 'dotfiles/home/bashrc' 'home/**/*.sh.tpl')";
    };

    # --- Markdown ---
    "lint:md:markdownlint" = {
      description = "Lint Markdown with markdownlint-cli2";
      exec = "markdownlint-cli2 .";
    };

    "fmt:md:markdownlint" = {
      description = "Auto-fix Markdown formatting with markdownlint-cli2";
      exec = "markdownlint-cli2 --fix .";
    };

    # --- Python ---
    "lint:python:ruff" = {
      description = "Lint Python with ruff";
      exec = "ruff check scripts_py tests";
    };

    "tests:python:pytest" = {
      description = "Run Python tests (pytest)";
      exec = "python -m pytest -q tests";
    };

    # --- Aggregates (for humans + CI) ---
    "lint:all" = {
      description = "All linters";
      after = [
        "lint:python:ruff"
        "lint:shell:shellcheck"
        "lint:yaml:yamllint"
        "lint:gha:actionlint"
        "lint:md:markdownlint"
      ];
      exec = "true";
    };

    "fmt:all" = {
      description = "All formatters";
      after = ["fmt:nix:alejandra" "fmt:md:markdownlint"];
      exec = "true";
    };

    "tests:all" = {
      description = "All tests";
      after = ["tests:python:pytest"];
      exec = "true";
    };

    "check:all" = {
      description = "Full repository check (CI equivalent)";
      after = ["check:nix:flake" "lint:all" "tests:all"];
      exec = "true";
    };
  };
}

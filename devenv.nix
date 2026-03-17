{pkgs, ...}: {
  # Keep devenv usable even when the user is not a trusted Nix user.
  # (Otherwise devenv tries to auto-manage Cachix config and can fail.)
  cachix.pull = ["nixos-setup-devenv"];
  cachix.push = "nixos-setup-devenv";

  dotenv.disableHint = true;

  packages = with pkgs; [
    git
    pre-commit
    alejandra
    yamllint
    check-jsonschema
    actionlint
    markdownlint-cli2
    shellcheck
    entr

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
      entry = "scripts/ensure-password-manager-login -- devenv tasks run check:nix:flake";
      language = "system";
      files = "(\\.nix$|^flake\\.nix$|^flake\\.lock$)";
      pass_filenames = false;
    };

    alejandra-fmt = {
      enable = true;
      name = "alejandra (nix fmt)";
      entry = "scripts/ensure-password-manager-login -- devenv tasks run fmt:nix:alejandra";
      language = "system";
      files = "(^flake\\.nix$|^(hosts|home|dev)/.*\\.nix$|.*\\.nix)";
      pass_filenames = false;
    };

    yamllint = {
      enable = true;
      name = "yamllint";
      entry = "scripts/ensure-password-manager-login -- devenv tasks run lint:yaml:yamllint";
      language = "system";
      files = ".*\\.ya?ml$";
      pass_filenames = false;
    };

    schemastore-schemas = {
      enable = true;
      name = "schemastore schema validation";
      # Calls the script directly (not via devenv task) so pre-commit can pass
      # only changed filenames for fast incremental validation.  The devenv task
      # lint:schemastore:validate runs --all instead.  Parity with check:all is
      # verified by tests/test_devenv_task_coverage.py (HOOK_TASK_OVERRIDES).
      entry = "scripts/ensure-password-manager-login -- scripts/validate-schemastore-schemas";
      language = "system";
      # Include extensionless YAML configs we have in-repo (e.g. .yamllint).
      files = "(^\\.yamllint$|.*\\.ya?ml$|.*\\.json$)";
      pass_filenames = true;
    };

    actionlint = {
      enable = true;
      name = "actionlint";
      entry = "scripts/ensure-password-manager-login -- devenv tasks run lint:gha:actionlint";
      language = "system";
      files = "^\\.github/workflows/.*\\.ya?ml$";
      pass_filenames = false;
    };

    shellcheck = {
      enable = true;
      name = "shellcheck";
      entry = "scripts/ensure-password-manager-login -- devenv tasks run lint:shell:shellcheck";
      language = "system";
      files = "(.*\\.sh$|^dotfiles/home/bashrc$|^home/.*\\.sh\\.tpl$)";
      pass_filenames = false;
    };

    markdownlint = {
      enable = true;
      name = "markdownlint";
      entry = "scripts/ensure-password-manager-login -- devenv tasks run lint:md:markdownlint";
      language = "system";
      files = ".*\\.md$";
      pass_filenames = false;
    };

    ruff-check = {
      enable = true;
      name = "ruff check";
      entry = "scripts/ensure-password-manager-login -- devenv tasks run lint:python:ruff";
      language = "system";
      files = ".*\\.py$";
      pass_filenames = false;
    };

    python-pytest = {
      enable = true;
      name = "pytest (cached)";
      # Uses file-level attestation caching: when all affected tests already
      # have a passing attestation (from the background watcher or a previous
      # commit attempt) the hook exits instantly.  Falls back to running pytest
      # on uncached test files.  PYTEST_ADDOPTS (--lf) still applies when
      # pytest actually runs.
      entry = "scripts/ensure-password-manager-login -- env PYTEST_ADDOPTS='--lf --lfnf=all' scripts/cached-pytest";
      language = "system";
      files = "(.*\\.py$|^devenv\\.nix$|^pyproject\\.toml$|^scripts/)";
      pass_filenames = false;
    };

    ci-check-all-attest = {
      enable = true;
      name = "CI equivalent checks (check:all)";
      entry = "scripts/ensure-password-manager-login -- scripts/attest-ci-checks --task check:all --push --no-run";
      language = "system";
      stages = ["pre-push"];
      pass_filenames = false;
    };
  };

  # Background test watcher: re-runs affected tests on file change and caches
  # attestations so the pre-commit hook can skip redundant runs.
  # Start with: devenv up  (or: devenv processes up)
  processes.test-watcher.exec = ''
    while true; do
      find scripts_py tests -name '*.py' | entr -d -p scripts/cached-pytest --watch
    done
  '';

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

    # --- SchemaStore (offline, vendored schemas) ---
    "sync:schemastore:index" = {
      description = "Update committed SchemaStore index + vendored schemas";
      exec = "scripts/sync-schemastore-index";
    };

    "lint:schemastore:validate" = {
      description = "Validate all indexed files against their SchemaStore schemas";
      exec = "scripts/validate-schemastore-schemas --all";
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

    "tests:python:cached-pytest" = {
      description = "Run Python tests with file-level attestation caching";
      exec = "scripts/cached-pytest";
    };

    # --- Tooling audit ---
    "audit:tooling" = {
      description = "Audit tooling coverage for all file types";
      exec = "scripts/audit-tooling";
    };

    "audit:tooling:strict" = {
      description = "Audit tooling coverage (strict — fails on unmuted gaps)";
      exec = "scripts/audit-tooling --strict";
    };

    # --- Aggregates (for humans + CI) ---
    "lint:all" = {
      description = "All linters";
      after = [
        "lint:python:ruff"
        "lint:shell:shellcheck"
        "lint:yaml:yamllint"
        "lint:schemastore:validate"
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

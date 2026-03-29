{pkgs, ...}: {
  # Keep devenv usable even when the user is not a trusted Nix user.
  # (Otherwise devenv tries to auto-manage Cachix config and can fail.)
  cachix.pull = ["tapiiri-nixos-setup-devenv"];
  cachix.push = "tapiiri-nixos-setup-devenv";

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
    shfmt
    taplo
    jq
    entr
    pyright

    # Python tooling pinned together (works even without devenv python module).
    (python313.withPackages (ps:
      with ps; [
        pytest
        ruff
        tomlkit

        # MkDocs documentation site
        mkdocs
        mkdocs-material
      ]))
  ];

  # Keep pre-commit as the runner (instead of the default prek).
  git-hooks.package = pkgs.pre-commit; # see devenv 1.11 changelog

  # Run hooks on merge commits too (Git 2.24+ calls pre-merge-commit instead of
  # pre-commit during `git merge`).  Without this, merges that bring in e.g.
  # flake.lock changes never trigger nix-flake-check, leaving the attestation
  # cache stale and causing the post-commit CI attestation to fail.
  git-hooks.default_stages = ["pre-commit" "pre-merge-commit"];

  git-hooks.hooks = {
    nix-flake-check = {
      enable = true;
      name = "nix flake check (cached)";
      # Uses file-level attestation caching: when all .nix files + flake.lock
      # match a previous passing attestation, the hook exits instantly.
      # Falls back to running ``nix flake check --no-build`` otherwise.
      entry = "scripts/ensure-password-manager-login -- scripts/cached-nix-check";
      language = "system";
      files = "(\\.nix$|^flake\\.nix$|^flake\\.lock$)";
      pass_filenames = false;
    };

    alejandra-fmt = {
      enable = true;
      name = "alejandra (nix fmt, cached)";
      entry = "scripts/ensure-password-manager-login -- scripts/cached-check --name alejandra --glob '**/*.nix' -- alejandra .";
      language = "system";
      files = "(^flake\\.nix$|^(hosts|home|dev)/.*\\.nix$|.*\\.nix)";
      pass_filenames = false;
    };

    yamllint = {
      enable = true;
      name = "yamllint (cached)";
      entry = "scripts/ensure-password-manager-login -- scripts/cached-check --name yamllint --glob '**/*.yml' --glob '**/*.yaml' --file .yamllint -- yamllint .";
      language = "system";
      files = ".*\\.ya?ml$";
      pass_filenames = false;
    };

    schemastore-schemas = {
      enable = true;
      name = "schemastore schema validation (cached)";
      # Uses cached-check for input-hash caching.  The devenv task
      # lint:schemastore:validate runs --all instead.  Parity with check:all is
      # verified by tests/test_devenv_task_coverage.py (HOOK_TASK_OVERRIDES).
      entry = "scripts/ensure-password-manager-login -- scripts/cached-check --name schemastore --glob '**/*.yml' --glob '**/*.yaml' --glob '**/*.json' --file schemas/schemastore-index.json -- scripts/validate-schemastore-schemas --all";
      language = "system";
      # Include extensionless YAML configs we have in-repo (e.g. .yamllint).
      files = "(^\\.yamllint$|.*\\.ya?ml$|.*\\.json$)";
      pass_filenames = false;
    };

    actionlint = {
      enable = true;
      name = "actionlint (cached)";
      entry = "scripts/ensure-password-manager-login -- scripts/cached-check --name actionlint --glob '.github/workflows/**/*.yml' --glob '.github/workflows/**/*.yaml' -- actionlint";
      language = "system";
      files = "^\\.github/workflows/.*\\.ya?ml$";
      pass_filenames = false;
    };

    shellcheck = {
      enable = true;
      name = "shellcheck (cached)";
      entry = "scripts/ensure-password-manager-login -- scripts/cached-check --name shellcheck --glob '**/*.sh' --file dotfiles/home/bashrc -- shellcheck $(git ls-files '*.sh' 'dotfiles/home/bashrc' 'home/**/*.sh.tpl')";
      language = "system";
      files = "(.*\\.sh$|^dotfiles/home/bashrc$|^home/.*\\.sh\\.tpl$)";
      pass_filenames = false;
    };

    shfmt = {
      enable = true;
      name = "shfmt (cached)";
      entry = "scripts/ensure-password-manager-login -- scripts/cached-check --name shfmt --glob '**/*.sh' --file dotfiles/home/bashrc -- shfmt -w -i 2 -ci $(git ls-files '*.sh' 'dotfiles/home/bashrc')";
      language = "system";
      files = "(.*\\.sh$|^dotfiles/home/bashrc$)";
      pass_filenames = false;
    };

    taplo-check = {
      enable = true;
      name = "taplo check (toml lint, cached)";
      entry = "scripts/ensure-password-manager-login -- scripts/cached-check --name taplo-check --glob '**/*.toml' -- taplo check $(git ls-files '*.toml')";
      language = "system";
      files = ".*\\.toml$";
      pass_filenames = false;
    };

    taplo-fmt = {
      enable = true;
      name = "taplo fmt (toml format, cached)";
      entry = "scripts/ensure-password-manager-login -- scripts/cached-check --name taplo-fmt --glob '**/*.toml' -- taplo fmt $(git ls-files '*.toml')";
      language = "system";
      files = ".*\\.toml$";
      pass_filenames = false;
    };

    jq-fmt = {
      enable = true;
      name = "jq (json format, cached)";
      entry = "scripts/ensure-password-manager-login -- scripts/cached-check --name jq-fmt --glob '**/*.json' -- devenv tasks run fmt:json:jq";
      language = "system";
      files = ".*\\.json$";
      pass_filenames = false;
    };

    markdownlint = {
      enable = true;
      name = "markdownlint (cached)";
      entry = "scripts/ensure-password-manager-login -- scripts/cached-check --name markdownlint --glob '**/*.md' --file .markdownlint-cli2.yaml -- markdownlint-cli2 .";
      language = "system";
      files = ".*\\.md$";
      pass_filenames = false;
    };

    ruff-check = {
      enable = true;
      name = "ruff check (cached)";
      entry = "scripts/ensure-password-manager-login -- scripts/cached-check --name ruff --glob 'scripts_py/**/*.py' --glob 'tests/**/*.py' --file pyproject.toml -- ruff check scripts_py tests";
      language = "system";
      files = ".*\\.py$";
      pass_filenames = false;
    };

    pyright-check = {
      enable = true;
      name = "pyright (cached)";
      entry = "scripts/ensure-password-manager-login -- scripts/cached-check --name pyright --glob 'scripts_py/**/*.py' --glob 'tests/**/*.py' --file pyproject.toml -- pyright scripts_py tests";
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

    mkdocs-build = {
      enable = true;
      name = "mkdocs build (cached)";
      entry = "scripts/ensure-password-manager-login -- scripts/cached-check --name mkdocs --glob 'docs/site/**' --file mkdocs.yml -- mkdocs build --strict";
      language = "system";
      files = "(^mkdocs\\.yml$|^docs/site/)";
      pass_filenames = false;
    };

    ci-attest-post-commit = {
      enable = true;
      name = "Post-commit CI attestation";
      # Verifies that local attestation caches (nix check + test results)
      # are fresh before writing a git-notes CI attestation.  If pre-commit
      # was skipped (--no-verify), caches will be stale/missing and the note
      # is NOT written, so CI runs normally.
      entry = "scripts/ensure-password-manager-login -- scripts/attest-ci-checks --task check:all --push --no-run --verify-local";
      language = "system";
      stages = ["post-commit"];
      always_run = true;
      pass_filenames = false;
    };
  };

  # Background test watcher: re-runs affected tests on file change and caches
  # attestations so the pre-commit hook can skip redundant runs.
  # VS Code users: this is optional — tests/conftest.py writes attestations
  # automatically whenever Test Explorer runs tests (enable auto-run for best
  # results).  This watcher is useful for terminal-only workflows.
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
      description = "nix flake check --no-build (with attestation)";
      exec = "scripts/cached-nix-check --force";
    };

    "fmt:nix:alejandra" = {
      description = "Format Nix files with alejandra (with attestation)";
      exec = "scripts/cached-check --name alejandra --glob '**/*.nix' --force -- alejandra .";
    };

    # --- YAML / GitHub Actions ---
    "lint:yaml:yamllint" = {
      description = "Lint YAML files with yamllint (with attestation)";
      exec = "scripts/cached-check --name yamllint --glob '**/*.yml' --glob '**/*.yaml' --file .yamllint --force -- yamllint .";
    };

    # --- SchemaStore (offline, vendored schemas) ---
    "sync:schemastore:index" = {
      description = "Update committed SchemaStore index + vendored schemas";
      exec = "scripts/sync-schemastore-index";
    };

    "lint:schemastore:validate" = {
      description = "Validate all indexed files against their SchemaStore schemas (with attestation)";
      exec = "scripts/cached-check --name schemastore --glob '**/*.yml' --glob '**/*.yaml' --glob '**/*.json' --file schemas/schemastore-index.json --force -- scripts/validate-schemastore-schemas --all";
    };

    "lint:gha:actionlint" = {
      description = "Lint GitHub Actions workflows with actionlint (with attestation)";
      exec = "scripts/cached-check --name actionlint --glob '.github/workflows/**/*.yml' --glob '.github/workflows/**/*.yaml' --force -- actionlint";
    };

    # --- Shell / templates ---
    "lint:shell:shellcheck" = {
      description = "Lint shell scripts with shellcheck (with attestation)";
      exec = "scripts/cached-check --name shellcheck --glob '**/*.sh' --file dotfiles/home/bashrc --force -- shellcheck $(git ls-files '*.sh' 'dotfiles/home/bashrc' 'home/**/*.sh.tpl')";
    };

    "fmt:shell:shfmt" = {
      description = "Format shell scripts with shfmt (with attestation)";
      exec = "scripts/cached-check --name shfmt --glob '**/*.sh' --file dotfiles/home/bashrc --force -- shfmt -w -i 2 -ci $(git ls-files '*.sh' 'dotfiles/home/bashrc')";
    };

    # --- TOML ---
    "lint:toml:taplo" = {
      description = "Lint TOML files with taplo (with attestation)";
      exec = "scripts/cached-check --name taplo-check --glob '**/*.toml' --force -- taplo check $(git ls-files '*.toml')";
    };

    "fmt:toml:taplo" = {
      description = "Format TOML files with taplo (with attestation)";
      exec = "scripts/cached-check --name taplo-fmt --glob '**/*.toml' --force -- taplo fmt $(git ls-files '*.toml')";
    };

    # --- JSON ---
    "lint:json:check-jsonschema" = {
      description = "Validate JSON files against SchemaStore schemas";
      after = ["lint:schemastore:validate"];
      exec = "true";
    };

    "fmt:json:jq" = {
      description = "Format JSON files with jq (with attestation)";
      exec = ''
        scripts/cached-check --name jq-fmt --glob '**/*.json' --force -- \
          bash -c 'for f in $(git ls-files "*.json" | grep -v "^\.vscode/"); do jq . "$f" > "$f.tmp" && mv "$f.tmp" "$f"; done'
      '';
    };

    # --- Markdown ---
    "lint:md:markdownlint" = {
      description = "Lint Markdown with markdownlint-cli2 (with attestation)";
      exec = "scripts/cached-check --name markdownlint --glob '**/*.md' --file .markdownlint-cli2.yaml --force -- markdownlint-cli2 .";
    };

    "fmt:md:markdownlint" = {
      description = "Auto-fix Markdown formatting with markdownlint-cli2";
      exec = "markdownlint-cli2 --fix .";
    };

    # --- Python ---
    "lint:python:ruff" = {
      description = "Lint Python with ruff (with attestation)";
      exec = "scripts/cached-check --name ruff --glob 'scripts_py/**/*.py' --glob 'tests/**/*.py' --file pyproject.toml --force -- ruff check scripts_py tests";
    };

    "lint:python:pyright" = {
      description = "Type-check Python with pyright (with attestation)";
      exec = "scripts/cached-check --name pyright --glob 'scripts_py/**/*.py' --glob 'tests/**/*.py' --file pyproject.toml --force -- pyright scripts_py tests";
    };

    "tests:python:pytest" = {
      description = "Run Python tests (pytest)";
      exec = "python -m pytest -q tests";
    };

    "tests:python:cached-pytest" = {
      description = "Run Python tests with file-level attestation caching";
      exec = "scripts/cached-pytest";
    };

    # --- Documentation ---
    "docs:mkdocs:build" = {
      description = "Build MkDocs site (with attestation)";
      exec = "scripts/cached-check --name mkdocs --glob 'docs/site/**' --file mkdocs.yml --force -- mkdocs build --strict";
    };

    "docs:mkdocs:serve" = {
      description = "Start MkDocs dev server";
      exec = "mkdocs serve";
    };

    "docs:all" = {
      description = "All documentation checks";
      after = ["docs:mkdocs:build"];
      exec = "true";
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
        "lint:python:pyright"
        "lint:shell:shellcheck"
        "lint:yaml:yamllint"
        "lint:schemastore:validate"
        "lint:gha:actionlint"
        "lint:md:markdownlint"
        "lint:toml:taplo"
        "lint:json:check-jsonschema"
      ];
      exec = "true";
    };

    "fmt:all" = {
      description = "All formatters";
      after = ["fmt:nix:alejandra" "fmt:md:markdownlint" "fmt:shell:shfmt" "fmt:toml:taplo" "fmt:json:jq"];
      exec = "true";
    };

    "tests:all" = {
      description = "All tests";
      after = ["tests:python:pytest"];
      exec = "true";
    };

    "check:all" = {
      description = "Full repository check (CI equivalent)";
      after = ["check:nix:flake" "lint:all" "tests:all" "docs:all"];
      exec = "true";
    };
  };
}

{
  pkgs,
  lib,
  config,
  ...
}: let
  cachixCaches = import ./cachix-caches.nix;

  renderCachedCheckArgs = flag: values:
    lib.concatMapStrings (value: " ${flag} ${lib.escapeShellArg value}") values;

  mkCachedCheckBase = check:
    "scripts/cached-check --name ${lib.escapeShellArg check.cacheName}"
    + renderCachedCheckArgs "--glob" check.globs
    + renderCachedCheckArgs "--file" (check.extraFiles or []);

  mkExec = check: "${mkCachedCheckBase check} -- ${check.cmd}";

  mkHookEntry = check: "${mkCachedCheckBase check} -- ${check.hookCmd or check.cmd}";

  mkHook = check:
    lib.nameValuePair check.hook.key {
      enable = true;
      name = check.hook.name;
      entry = mkHookEntry check;
      language = "system";
      files = check.hook.files;
      pass_filenames = false;
    };

  # Default ignore patterns for all watchers.
  defaultWatchIgnore = [".git" "result" "__pycache__" ".pytest_cache"];

  # Build a watchexec command that wraps the cached-check in a long-running
  # file watcher.  devenv's native `watch` doesn't work for one-shot commands
  # (the supervisor kills the file watcher when the process exits), so we use
  # watchexec directly instead.
  mkWatchExec = check: let
    w = check.process.watch;
    ignores = lib.unique (defaultWatchIgnore ++ (w.ignore or []));
    pathArgs = lib.concatMapStrings (p: " --watch ${lib.escapeShellArg p}") w.paths;
    extArg =
      if w.extensions or [] != []
      then " -e ${lib.concatStringsSep "," w.extensions}"
      else "";
    ignoreArgs = lib.concatMapStrings (i: " --ignore ${lib.escapeShellArg i}") ignores;
  in "watchexec --shell=none --no-vcs-ignore${pathArgs}${extArg}${ignoreArgs} -- ${mkExec check}";

  mkProcess = check:
    lib.nameValuePair check.process.key {
      exec = mkWatchExec check;
      process-compose = {
        namespace = check.process.namespace;
      };
    };

  mkTask = check:
    lib.nameValuePair check.task.key {
      description = check.task.description;
      exec = mkExec check;
    };

  cachedChecks = [
    {
      # Fast pure-Python check: verifies every flake.nix input has a flake.lock entry.
      # Catches the failure mode where a new input is staged without running `nix flake lock`.
      cacheName = "check-flake-lock";
      globs = [];
      extraFiles = ["flake.nix" "flake.lock"];
      cmd = "scripts/check-flake-lock";
      hook = {
        key = "check-flake-lock";
        name = "check flake.lock completeness";
        files = "(^flake\\.nix$|^flake\\.lock$)";
      };
      process = null;
      task = {
        key = "lint:nix:flake-lock";
        description = "Check that flake.lock has entries for all flake.nix inputs";
      };
    }
    {
      cacheName = "nix-flake-check";
      globs = ["**/*.nix"];
      extraFiles = ["flake.lock"];
      # Scoped to CI-safe outputs: base host + packages.
      # fw12/fw16 are evaluated by check:nix:host:fw12/fw16 (local-only,
      # requires the private vaisala-pilot input).
      cmd = "bash -c 'nix eval .#nixosConfigurations.base.config.system.build.toplevel --no-write-lock-file && nix eval .#packages.x86_64-linux --apply builtins.attrNames --no-write-lock-file'";
      hook = {
        key = "nix-flake-check";
        name = "nix eval base + packages (cached)";
        files = "(\\.nix$|^flake\\.nix$|^flake\\.lock$)";
      };
      process = {
        key = "watch-nix";
        namespace = "nix";
        watch = {
          paths = [config.git.root];
          extensions = ["nix" "lock"];
          ignore = [".git" "result"];
        };
      };
      task = {
        key = "check:nix:flake";
        description = "Evaluate base NixOS config and packages (CI-safe, with attestation)";
      };
    }
    {
      # Local-only: evaluates fw12 NixOS config.
      # Requires the private vaisala-pilot flake input — never runs in CI.
      cacheName = "nix-host-fw12";
      globs = ["**/*.nix"];
      extraFiles = ["flake.lock"];
      cmd = "nix eval .#nixosConfigurations.fw12.config.system.build.toplevel --no-write-lock-file";
      hook = {
        key = "nix-host-fw12";
        name = "nix eval nixosConfigurations.fw12 (cached)";
        files = "(\\.nix$|^flake\\.lock$)";
      };
      process = null;
      task = {
        key = "check:nix:host:fw12";
        description = "Evaluate fw12 NixOS configuration (local-only, requires vaisala-pilot)";
      };
    }
    {
      # Local-only: evaluates fw16 NixOS config.
      # Requires the private vaisala-pilot flake input — never runs in CI.
      cacheName = "nix-host-fw16";
      globs = ["**/*.nix"];
      extraFiles = ["flake.lock"];
      cmd = "nix eval .#nixosConfigurations.fw16.config.system.build.toplevel --no-write-lock-file";
      hook = {
        key = "nix-host-fw16";
        name = "nix eval nixosConfigurations.fw16 (cached)";
        files = "(\\.nix$|^flake\\.lock$)";
      };
      process = null;
      task = {
        key = "check:nix:host:fw16";
        description = "Evaluate fw16 NixOS configuration (local-only, requires vaisala-pilot)";
      };
    }
    {
      cacheName = "nix-homes-eval";
      globs = ["**/*.nix"];
      extraFiles = ["flake.lock"];
      cmd = "bash -c 'nix eval .#homeConfigurations.tapiiri.activationPackage --no-write-lock-file && nix eval \".#homeConfigurations.tapiiri-wsl.activationPackage\" --no-write-lock-file && nix eval .#homeConfigurations.ilmari.activationPackage --no-write-lock-file'";
      hook = {
        key = "nix-homes-eval";
        name = "nix eval homeConfigurations (cached)";
        files = "(\\.nix$|^flake\\.lock$)";
      };
      process = null;
      task = {
        key = "check:nix:homes";
        description = "Evaluate all home configurations (catches insecure packages and eval errors)";
      };
    }
    {
      cacheName = "alejandra";
      globs = ["**/*.nix"];
      cmd = "alejandra .";
      hook = {
        key = "alejandra-fmt";
        name = "alejandra (nix fmt, cached)";
        files = "(^flake\\.nix$|^(hosts|home|dev)/.*\\.nix$|.*\\.nix)";
      };
      process = null;
      task = {
        key = "fmt:nix:alejandra";
        description = "Format Nix files with alejandra (with attestation)";
      };
    }
    {
      cacheName = "yamllint";
      globs = ["**/*.yml" "**/*.yaml"];
      extraFiles = [".yamllint"];
      cmd = "yamllint .";
      hook = {
        key = "yamllint";
        name = "yamllint (cached)";
        files = ".*\\.ya?ml$";
      };
      process = {
        key = "watch-yamllint";
        namespace = "lint";
        watch = {
          paths = [config.git.root];
          extensions = ["yml" "yaml"];
          ignore = [".git" "result" "site"];
        };
      };
      task = {
        key = "lint:yaml:yamllint";
        description = "Lint YAML files with yamllint (with attestation)";
      };
    }
    {
      cacheName = "schemastore";
      globs = ["**/*.yml" "**/*.yaml" "**/*.json"];
      extraFiles = ["schemas/schemastore-index.json"];
      cmd = "scripts/validate-schemastore-schemas --all";
      hook = {
        key = "schemastore-schemas";
        name = "schemastore schema validation (cached)";
        files = "(^\\.yamllint$|.*\\.ya?ml$|.*\\.json$)";
      };
      process = {
        key = "watch-schemastore";
        namespace = "lint";
        watch = {
          paths = [config.git.root];
          extensions = ["yml" "yaml" "json"];
          ignore = [".git" "result" "site"];
        };
      };
      task = {
        key = "lint:schemastore:validate";
        description = "Validate all indexed files against their SchemaStore schemas (with attestation)";
      };
    }
    {
      cacheName = "actionlint";
      globs = [".github/workflows/**/*.yml" ".github/workflows/**/*.yaml"];
      cmd = "actionlint";
      hook = {
        key = "actionlint";
        name = "actionlint (cached)";
        files = "^\\.github/workflows/.*\\.ya?ml$";
      };
      process = {
        key = "watch-actionlint";
        namespace = "lint";
        watch = {
          paths = ["${config.git.root}/.github/workflows"];
          extensions = ["yml" "yaml"];
        };
      };
      task = {
        key = "lint:gha:actionlint";
        description = "Lint GitHub Actions workflows with actionlint (with attestation)";
      };
    }
    {
      cacheName = "shellcheck";
      globs = ["**/*.sh"];
      extraFiles = ["dotfiles/home/bashrc"];
      cmd = "shellcheck $(git ls-files '*.sh' 'dotfiles/home/bashrc' 'home/**/*.sh.tpl')";
      hook = {
        key = "shellcheck";
        name = "shellcheck (cached)";
        files = "(.*\\.sh$|^dotfiles/home/bashrc$|^home/.*\\.sh\\.tpl$)";
      };
      process = {
        key = "watch-shellcheck";
        namespace = "lint";
        watch = {
          paths = ["${config.git.root}/dotfiles" "${config.git.root}/home" "${config.git.root}/scripts"];
          extensions = ["sh" "tpl"];
        };
      };
      task = {
        key = "lint:shell:shellcheck";
        description = "Lint shell scripts with shellcheck (with attestation)";
      };
    }
    {
      cacheName = "shfmt";
      globs = ["**/*.sh"];
      extraFiles = ["dotfiles/home/bashrc"];
      cmd = "shfmt -w -i 2 -ci $(git ls-files '*.sh' 'dotfiles/home/bashrc')";
      hook = {
        key = "shfmt";
        name = "shfmt (cached)";
        files = "(.*\\.sh$|^dotfiles/home/bashrc$)";
      };
      process = null;
      task = {
        key = "fmt:shell:shfmt";
        description = "Format shell scripts with shfmt (with attestation)";
      };
    }
    {
      cacheName = "taplo-check";
      globs = ["**/*.toml"];
      cmd = "taplo check $(git ls-files '*.toml')";
      hook = {
        key = "taplo-check";
        name = "taplo check (toml lint, cached)";
        files = ".*\\.toml$";
      };
      process = {
        key = "watch-taplo";
        namespace = "lint";
        watch = {
          paths = [config.git.root];
          extensions = ["toml"];
          ignore = [".git" "result"];
        };
      };
      task = {
        key = "lint:toml:taplo";
        description = "Lint TOML files with taplo (with attestation)";
      };
    }
    {
      cacheName = "taplo-fmt";
      globs = ["**/*.toml"];
      cmd = "taplo fmt $(git ls-files '*.toml')";
      hook = {
        key = "taplo-fmt";
        name = "taplo fmt (toml format, cached)";
        files = ".*\\.toml$";
      };
      process = null;
      task = {
        key = "fmt:toml:taplo";
        description = "Format TOML files with taplo (with attestation)";
      };
    }
    {
      cacheName = "jq-fmt";
      globs = ["**/*.json"];
      cmd = "bash -c 'for f in $(git ls-files \"*.json\" | grep -v \"^\\.vscode/\"); do jq . \"$f\" > \"$f.tmp\" && mv \"$f.tmp\" \"$f\"; done'";
      hookCmd = "devenv tasks run fmt:json:jq";
      hook = {
        key = "jq-fmt";
        name = "jq (json format, cached)";
        files = ".*\\.json$";
      };
      process = null;
      task = {
        key = "fmt:json:jq";
        description = "Format JSON files with jq (with attestation)";
      };
    }
    {
      cacheName = "markdownlint";
      globs = ["**/*.md"];
      extraFiles = [".markdownlint-cli2.yaml"];
      cmd = "markdownlint-cli2 .";
      hook = {
        key = "markdownlint";
        name = "markdownlint (cached)";
        files = ".*\\.md$";
      };
      process = {
        key = "watch-markdownlint";
        namespace = "lint";
        watch = {
          paths = [config.git.root];
          extensions = ["md" "yaml"];
          ignore = [".git" "result" "site"];
        };
      };
      task = {
        key = "lint:md:markdownlint";
        description = "Lint Markdown with markdownlint-cli2 (with attestation)";
      };
    }
    {
      cacheName = "ruff";
      globs = ["scripts_py/**/*.py" "tests/**/*.py"];
      extraFiles = ["pyproject.toml"];
      cmd = "ruff check scripts_py tests";
      hook = {
        key = "ruff-check";
        name = "ruff check (cached)";
        files = ".*\\.py$";
      };
      process = {
        key = "watch-ruff";
        namespace = "python";
        watch = {
          paths = ["${config.git.root}/scripts_py" "${config.git.root}/tests"];
          extensions = ["py" "toml"];
        };
      };
      task = {
        key = "lint:python:ruff";
        description = "Lint Python with ruff (with attestation)";
      };
    }
    {
      cacheName = "pyright";
      globs = ["scripts_py/**/*.py" "tests/**/*.py"];
      extraFiles = ["pyproject.toml"];
      cmd = "pyright scripts_py tests";
      hook = {
        key = "pyright-check";
        name = "pyright (cached)";
        files = ".*\\.py$";
      };
      process = {
        key = "watch-pyright";
        namespace = "python";
        watch = {
          paths = ["${config.git.root}/scripts_py" "${config.git.root}/tests"];
          extensions = ["py" "toml"];
        };
      };
      task = {
        key = "lint:python:pyright";
        description = "Type-check Python with pyright (with attestation)";
      };
    }
    {
      cacheName = "pytest";
      globs = ["scripts_py/**/*.py" "tests/**/*.py"];
      extraFiles = ["pyproject.toml" "devenv.nix"];
      cmd = "python -m pytest -q tests";
      hook = {
        key = "python-pytest";
        name = "pytest (cached)";
        files = "(.*\\.py$|^devenv\\.nix$|^pyproject\\.toml$|^scripts/)";
      };
      process = {
        key = "watch-pytest";
        namespace = "python";
        watch = {
          paths = ["${config.git.root}/scripts_py" "${config.git.root}/tests" "${config.git.root}/scripts"];
          extensions = ["py" "nix" "toml"];
        };
      };
      task = {
        key = "tests:python:pytest";
        description = "Run Python tests with attestation caching";
      };
    }
    {
      cacheName = "mkdocs";
      globs = ["docs/site/**"];
      extraFiles = ["mkdocs.yml"];
      cmd = "mkdocs build --strict";
      hook = {
        key = "mkdocs-build";
        name = "mkdocs build (cached)";
        files = "(^mkdocs\\.yml$|^docs/site/)";
      };
      process = {
        key = "watch-mkdocs";
        namespace = "docs";
        watch = {
          paths = ["${config.git.root}/docs/site"];
          extensions = ["md"];
        };
      };
      task = {
        key = "docs:mkdocs:build";
        description = "Build MkDocs site (with attestation)";
      };
    }
  ];

  generatedHooks = lib.listToAttrs (map mkHook cachedChecks);

  generatedProcesses = lib.listToAttrs (
    map mkProcess (lib.filter (check: check.process != null) cachedChecks)
  );

  generatedTasks = lib.listToAttrs (map mkTask cachedChecks);
in {
  # Keep devenv usable even when the user is not a trusted Nix user.
  # (Otherwise devenv tries to auto-manage Cachix config and can fail.)
  cachix.pull = [cachixCaches.devenv.name];
  # Push is CI-only — see .github/workflows/ci.yml (devenv.local.nix step).

  dotenv.disableHint = true;

  packages = with pkgs; [
    git
    pre-commit
    alejandra
    yamllint
    watchexec
    check-jsonschema
    actionlint
    markdownlint-cli2
    shellcheck
    shfmt
    taplo
    jq
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

  git-hooks.hooks =
    generatedHooks
    // {
      ci-attest-post-commit = {
        enable = true;
        name = "Post-commit CI attestation";
        # Verifies that local attestation caches (nix check + test results)
        # are fresh before writing a git-notes CI attestation.  If all caches
        # are fresh (pre-commit ran), the note is written instantly.
        #
        # Auto-recovery: when caches are stale (e.g. after merging a PR that
        # updated flake.lock, or after a --no-verify commit), the hook
        # automatically runs check:all to re-seed caches and retries
        # verification.  This is slower (~1 min) but ensures attestation
        # is not permanently broken by one skipped hook run.
        entry = "scripts/attest-ci-checks --task check:all --verify-local";
        language = "system";
        stages = ["post-commit"];
        always_run = true;
        pass_filenames = false;
      };

      ci-attest-pre-push = {
        enable = true;
        name = "Push CI attestation notes to remote";
        # Pushes the local git-notes attestation ref to origin so that
        # ci-attestation-gate can read it.  Best-effort: failure is logged
        # but never blocks the push.
        entry = "scripts/attest-ci-checks --push-only";
        language = "system";
        stages = ["pre-push"];
        always_run = true;
        pass_filenames = false;
      };
    };

  # Background check watchers: run all cached checks when their inputs change,
  # pre-warming attestation caches so the pre-commit hook can skip redundant runs.
  # VS Code users: tests/conftest.py writes test attestations via Test Explorer;
  # these watchers additionally cover lint and nix checks.
  # Formatters are excluded to avoid unintended background file modifications.
  # Start with: devenv up  (or: devenv processes up)
  processes = generatedProcesses;

  # Canonical automation entrypoints.
  #
  # Conventions:
  # - Tasks are namespaced (e.g. "lint:python:ruff") so they compose well.
  # - pre-commit hooks should delegate to these tasks to avoid duplicating logic.
  tasks =
    generatedTasks
    // {
      # --- SchemaStore (offline, vendored schemas) ---
      "sync:schemastore:index" = {
        description = "Update committed SchemaStore index + vendored schemas";
        exec = "scripts/sync-schemastore-index";
      };

      # --- JSON ---
      "lint:json:check-jsonschema" = {
        description = "Validate JSON files against SchemaStore schemas";
        after = ["lint:schemastore:validate"];
        exec = "true";
      };

      # --- Markdown ---
      "fmt:md:markdownlint" = {
        description = "Auto-fix Markdown formatting with markdownlint-cli2";
        exec = "markdownlint-cli2 --fix .";
      };

      # --- Documentation ---
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
          "lint:nix:flake-lock"
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
        after = ["check:nix:flake" "check:nix:homes" "lint:all" "tests:all" "docs:all"];
        exec = "true";
      };
    };
}

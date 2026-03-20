{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;

  jsonFormat = pkgs.formats.json {};

  # Keep VS Code settings in one place. We only apply them when VS Code is enabled
  # somewhere else (e.g. `my.devtools.enable` sets `programs.vscode.enable = true`).
  vscodeEnabled = config.programs.vscode.enable or false;

  # VS Code needs a path to the formatter binary for Nix files.
  alejandraBin = lib.getExe pkgs.alejandra;
  nilBin = lib.getExe pkgs.nil;

  # Extension IDs are `publisher.extensionName`.
  nixIdeExt = pkgs.vscode-extensions.jnoortheen.nix-ide;
  markdownlintExt = pkgs.vscode-extensions.davidanson.vscode-markdownlint;
  GHActionsExt = pkgs.vscode-extensions.github.vscode-github-actions;
  GHPullRequestsExt = pkgs.vscode-extensions.github.vscode-pull-request-github;
  CopilotExt = pkgs.vscode-extensions.github.copilot;
  ActionsExt = pkgs.vscode-extensions.github.vscode-github-actions;

  # Other repo/devtools helpers.
  PythonExt = pkgs.vscode-extensions.ms-python.python;
  PylanceExt = pkgs.vscode-extensions.ms-python.vscode-pylance;
  ShellCheckExt = pkgs.vscode-extensions.timonwong.shellcheck;
  YamlExt = pkgs.vscode-extensions.redhat.vscode-yaml;
  TomlExt = pkgs.vscode-extensions.tamasfe.even-better-toml;
  EditorConfigExt = pkgs.vscode-extensions.editorconfig.editorconfig;
  RuffExt = pkgs.vscode-extensions.charliermarsh.ruff;
  DirenvExt = pkgs.vscode-extensions.mkhl.direnv;

  # Auto-run tests on file save (triggers VS Code Test Explorer, which writes
  # attestations via tests/conftest.py).  Not packaged in nixpkgs.
  RunOnSaveExt = pkgs.vscode-utils.buildVscodeMarketplaceExtension {
    mktplcRef = {
      publisher = "pucelle";
      name = "run-on-save";
      version = "1.11.2";
      hash = "sha256-SnaQpOWBjLbzu/HLLwFhj7RsVO3k5gZwsQgk0S+SK0Y=";
    };
  };

  # 1Password VS Code extension (not packaged in nixpkgs in this repo's snapshot).
  OnePasswordExt = pkgs.vscode-utils.buildVscodeMarketplaceExtension {
    mktplcRef = {
      # Marketplace publisher uses this casing.
      publisher = "1Password";
      name = "op-vscode";
      # Pin this after first build: set a dummy hash, build once, then copy the
      # reported sha256 here.
      version = "1.0.5";
      # NOTE: This must be an SRI hash. Use any dummy value, build once, then
      # replace with the reported `got: sha256-...`.
      hash = "sha256-J7vAK2t6fSjm5i6y3+88aO84ipFwekQkJMD7W3EIWrc=";
    };
  };
  # Not packaged in nixpkgs (no `pkgs.vscode-extensions.openai.*`), so fetch it
  # from the VS Code Marketplace and build a Nix derivation instead.
  CodexExt = pkgs.vscode-utils.buildVscodeMarketplaceExtension {
    mktplcRef = {
      publisher = "openai";
      name = "chatgpt";
      # Pin this after first build: set a dummy hash, build once, then copy the
      # reported sha256 here.
      version = "0.5.56";
      hash = "sha256-FAy2Cf2XnOnctBBATloXz8y4cLNHBoXAVnlw42CQzN8=";
    };
  };

  # Settings used by nix-ide / VS Code Nix tooling.
  # These are "structural" settings that point to binaries and configure tooling.
  # They should be managed declaratively by home-manager.
  vscodeNixSettings = {
    # Disable prompts for updates.
    "update.mode" = "none";

    # Disable extensions auto-update to avoid unexpected changes.
    "extensions.autoUpdate" = false;

    # Format on save globally.
    "editor.formatOnSave" = true;

    # Be explicit about *when* formatting runs on save. VS Code defaults can vary
    # and extensions may add additional formatting providers; this keeps behavior
    # consistent.
    #
    # - file: always format the whole file
    "editor.formatOnSaveMode" = "file";

    # Repo convention: dev tooling comes from `devenv.nix`.
    "nixEnvSelector.nixFile" = "devenv.nix";

    # Enable native Python test explorer (inline pass/fail, gutter decorations).
    "python.testing.pytestEnabled" = true;
    "python.testing.pytestArgs" = ["tests"];
    "python.testing.autoTestDiscoverOnSaveEnabled" = true;

    # Pylance type checking: use pyright strict mode (matches pyproject.toml).
    # Pylance uses pyright under the hood; this gives inline type errors in the editor.
    "python.analysis.typeCheckingMode" = "strict";
    "python.analysis.diagnosticSeverityOverrides" = {};

    # Auto-run all tests on every .py save via pucelle.run-on-save.
    # The Python extension doesn't natively support VS Code's continuous-run
    # API, so we use this extension to trigger testing.runAll on save.
    # Our tests/conftest.py plugin writes attestations on each run, keeping
    # the pre-commit hook fast.
    "runOnSave.commands" = [
      {
        match = ".*\\.py$";
        command = "testing.runAll";
        runIn = "vscode";
      }
    ];

    # Use alejandra for Nix formatting.
    "[nix]" = {
      "editor.defaultFormatter" = "jnoortheen.nix-ide";
      "editor.formatOnSave" = true;
    };

    # nix-ide settings.
    "nix.enableLanguageServer" = true;
    "nix.serverPath" = nilBin;
    "nix.formatterPath" = alejandraBin;

    # Helpful, conservative defaults.
    "nix.serverSettings" = {
      nil = {
        # nil supports formatting via external formatter.
        formatting = {command = [alejandraBin];};
      };
    };
  };

  # User-specific settings that VS Code may modify at runtime.
  # To capture VS Code's runtime changes and integrate them here,
  # run: ./scripts/sync-vscode-settings
  # This will generate user-settings.nix with any new settings.
  vscodeUserSettingsPath = ./user-settings.nix;
  vscodeUserSettings =
    if builtins.pathExists vscodeUserSettingsPath
    then (import vscodeUserSettingsPath).userSettings
    else {};

  # Merge structural and user settings
  # Note: home-manager will write these to settings.json on each rebuild,
  # overwriting any manual changes. To preserve manual changes, sync them
  # back to this Nix config using ./scripts/sync-vscode-settings
  allVscodeSettings = vscodeNixSettings // vscodeUserSettings;

  # Generate a proper JSON file in the Nix store rather than embedding JSON
  # into the activation script. This keeps this module readable and makes the
  # "template" a real file.
  vscodeSettingsTemplate = jsonFormat.generate "vscode-settings.json" allVscodeSettings;

  vscodeManagedSettingsJson = builtins.toJSON vscodeNixSettings;

  vscodeSettingsActivationScript = pkgs.replaceVars ./activation-vscode-settings.sh.tpl {
    SETTINGS_TEMPLATE = "${vscodeSettingsTemplate}";
    MANAGED_SETTINGS_JSON = vscodeManagedSettingsJson;
    JQ_BIN = "${pkgs.jq}/bin/jq";
  };
in {
  options.my.vscode = {
    enable = mkEnableOption "VS Code configuration (extensions + settings)";
  };

  config = mkIf (config.my.vscode.enable && vscodeEnabled) {
    programs.vscode = {
      # We intentionally *don't* set `enable = true` here; devtools (or another module)
      # is responsible for that.

      # Allow VS Code to manage extensions directory (mutable)
      mutableExtensionsDir = true;

      # Install extensions using the new profiles syntax.
      profiles.default.extensions = [
        nixIdeExt
        markdownlintExt
        GHActionsExt
        GHPullRequestsExt
        CopilotExt
        CodexExt
        DirenvExt
        PythonExt
        PylanceExt
        ShellCheckExt
        YamlExt
        TomlExt
        EditorConfigExt
        OnePasswordExt
        RuffExt
        ActionsExt
        RunOnSaveExt
      ];

      # IMPORTANT: Do NOT set userSettings here.
      # Home Manager's VS Code module writes settings.json as a symlink into the
      # Nix store, which makes it read-only for VS Code.
      #
      # We manage settings.json ourselves via the activation script below.
    };

    # Use an activation script to merge our base settings with any existing user settings
    # This allows VS Code to modify settings.json while we provide defaults
    # Run *after* Home Manager's built-in VS Code profile activation, because
    # that step may (re)create settings.json as a Nix store symlink.
    # We then replace it with a writable file and merge managed settings.
    home.activation.vscodeSettings = lib.hm.dag.entryAfter ["vscodeProfiles"] ''
      # Delegate the actual activation logic to a real template file rendered by Nix.
      # shellcheck source=/dev/null
      source "${vscodeSettingsActivationScript}"
    '';
  };
}

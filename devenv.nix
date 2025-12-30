{pkgs, ...}: {
  # Keep devenv usable even when the user is not a trusted Nix user.
  # (Otherwise devenv tries to auto-manage Cachix config and can fail.)
  cachix.enable = false;

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
      ]))
  ];

  scripts = {
    test.exec = "python -m pytest -q";
    lint.exec = "pre-commit run --all-files";
  };

  enterShell = ''
    if [ -d .git ] && [ ! -x .git/hooks/pre-commit ]; then
      echo "Installing pre-commit hooks (via devenv) ..."
      pre-commit install --install-hooks >/dev/null || true
    fi
  '';
}

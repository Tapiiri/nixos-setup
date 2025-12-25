# nixos-setup

## Repo scripts

Some helper scripts live under `scripts/`. They are designed to be runnable as normal executables (for example `rebuild`, including via `sudo`) and implemented in Python for testability.

### Python version and dependencies

Python tooling for this repo is provided via Home Manager when `my.devtools.enable = true`.

- Python is pinned in `home/modules/devtools.nix` (currently `pkgs.python313`).
- Script/test dependencies (like `pytest`/`ruff` if used) should be added there via `py.pkgs`.

### Running tests

This repo’s unit tests use the Python standard library `unittest`, so they work in minimal environments.

Run:

- `python -m unittest -q`

If you prefer pytest locally, you can add it in `home/modules/devtools.nix` (already included) and run:

- `pytest -q`

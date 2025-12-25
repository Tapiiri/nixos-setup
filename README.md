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

If you run into `ModuleNotFoundError: No module named 'pytest'` even though `pytest` is on PATH, you're typically picking up a `pytest` launcher that points at a different Python than the one in your current shell session.

Most reliable options:

- Use the interpreter module form:
	- `python -m pytest -q`
- Or use the repo's dev-only flake shell (pins Python + pytest together without touching the NixOS flake outputs):
	- `nix develop ./dev -c pytest -q`

If you want an interactive shell (so you can just type `pytest` afterwards), enter it first and then run commands normally:

- `nix develop ./dev`
- then: `pytest -q`

There's also a convenience wrapper script:

- `./scripts/devshell`
- then: `pytest -q`

Optional: if you use `direnv`, you can add an `.envrc` that auto-enters the dev shell on `cd`.

### PATH troubleshooting (why `rebuild` isn't found)

Scripts from `scripts/` are linked into `~/.local/bin` by `scripts/setup-links.sh`.
For the commands to be found, `~/.local/bin` must be in your `$PATH`.

In this setup, `~/.local/bin` is exported via Home Manager session variables
(`home.sessionPath` / `hm-session-vars.sh`). If your PATH looked correct in one
session but changed after reboot, the most common cause is that your shell
isn't sourcing Home Manager's session vars.

Quick checks:

- `echo "$PATH" | grep -q "$HOME/.local/bin" && echo OK || echo MISSING`
- `test -f "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh" && echo OK || echo MISSING`

This repo's module `home/modules/shell-bash.nix` sources `hm-session-vars.sh`
for both login shells and interactive shells.

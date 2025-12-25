# Dotfiles

This repo can manage personal dotfiles by symlinking them into place via `scripts/setup-links.sh`.

## Layout

This repo primarily follows **Model A**: Home Manager / Nix is the source of truth.

Dotfiles here are meant for a small set of explicit "raw" files (typically under `$HOME`).

Currently supported:

- `dotfiles/home/*` → `$HOME/.*`
  - Example: `dotfiles/home/gitconfig` → `~/.gitconfig`
  - Example: `dotfiles/home/bashrc` → `~/.bashrc`

Each *top-level entry* under that folder is linked as-is (file or directory).

## Usage

Run the normal link script (it now also processes dotfiles):

- `scripts/setup-links.sh --host <hostname>`

If you also want it to link the host NixOS files into `/etc/nixos`, provide a root helper:

- `scripts/setup-links.sh --host <hostname> --root-helper sudo`

## Notes / safety

- The script is idempotent: if the target already points to the right source, it does nothing.
- If a target path already exists and is not the right symlink, it will be replaced (a warning is printed).
- The script creates parent directories as needed.

## Sync direction (important)

Symlinking is "repo → system": when you edit the config through the *linked path* (for example edit `~/.bashrc` once it is a symlink), you are actually editing the file inside this repo.

However, changes made to a *non-linked copy* elsewhere won’t automatically be copied back into this repo.

If you want to import existing configs from your system into the repo, use `scripts/import-dotfiles`.

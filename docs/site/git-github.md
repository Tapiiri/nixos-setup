# Git & GitHub

This repo configures Git via Home Manager and provides scripts for managing
GitHub repository settings.

## Git defaults

Git is configured in `home/modules/git.nix` via Home Manager. Notable defaults:

### Pull strategy

```ini
[pull]
    rebase = false
```

When histories diverge, `git pull` uses **merge** (not rebase). This avoids
accidental history rewrites on personal branches.

### SSH commit signing

Optional SSH-based commit signing using `ed25519`. If you enable signing but
Git can't find the key, you'll see:

> `fatal: either user.signingkey or gpg.ssh.defaultKeyCommand needs to be configured`

**Setup:**

```bash
# Generate a dedicated signing key
ssh-keygen -t ed25519 -C "git-signing" -f ~/.ssh/id_ed25519_git_signing
```

Then:

1. Add the **public key** to GitHub as a **Signing key** (not an Authentication key)
2. Configure via Home Manager in `home/modules/git.nix`

## GitHub labels

This repo keeps its label catalog in `.github/labels.yml` and provides a sync
script that uses the `gh` CLI to keep GitHub labels consistent.

### Usage

```bash
# Preview what would change
scripts/sync-github-labels --dry-run

# Apply changes
scripts/sync-github-labels
```

### Flags

| Flag | Description |
|------|-------------|
| `--repo OWNER/REPO` | Target a specific repo (defaults to `gh`-detected repo) |
| `--dry-run` | Show what would change without making changes |
| `--delete-unmanaged` | Delete labels not listed in `labels.yml` |

!!! warning
    `--delete-unmanaged` will remove any manually-created labels. Use with caution.

### Why this exists

Dependabot and some GitHub Actions workflows expect certain labels to exist
(e.g. `dependencies`, `github-actions`). Keeping them in version control
prevents "label not found" errors in automation.

## GitHub Pages

The docs site is deployed via GitHub Pages using GitHub Actions.

The `setup-github-pages` script configures the Pages environment programmatically:

```bash
scripts/setup-github-pages
```

It uses the `gh` API to set the Pages build source to "GitHub Actions" (rather
than deploying from a branch). This is idempotent — safe to run multiple times.

## GitHub environment variables

The `update-github-env` script manages GitHub environment variables:

```bash
scripts/update-github-env
```

This is used to keep CI environment configuration in sync with the repo's
expected values.

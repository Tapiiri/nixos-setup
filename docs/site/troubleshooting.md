# Troubleshooting

Common issues and how to fix them.

## PATH issues

### Scripts not found after `setup-links`

If `rebuild` or other scripts aren't found, `~/.local/bin` probably isn't on
`$PATH`.

**Quick check:**

```bash
echo "$PATH" | grep -q "$HOME/.local/bin" && echo OK || echo MISSING
```

**Fix:** This repo's Home Manager bash module sources `hm-session-vars.sh` for
both login and interactive shells. Verify it exists:

```bash
test -f "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh" && echo OK || echo MISSING
```

If it's missing, you may need to run a Home Manager rebuild first. If it exists
but `~/.local/bin` still isn't on PATH, check that your shell config sources it
(usually handled automatically by HM's bash module).

## Rebuild issues

### "Could not find flake.nix in /etc/nixos"

`rebuild` defaults to `/etc/nixos` as the flake source. If it's empty or not
set up:

| Fix | Command |
|-----|---------|
| Bootstrap via mirror (recommended) | Run `rebuild` once while online |
| Use local checkout | `rebuild --dev` |
| Point explicitly | `rebuild --flake /path/to/flake` |

See the [Rebuild guide](guides/rebuild.md) for the full mirror workflow.

### "Refusing to overwrite existing git repo at /etc/nixos"

In mirror mode, `rebuild` refuses to overwrite an existing Git repo. This is a
safety check. If you truly intend to replace it, move the existing repo aside
manually:

```bash
sudo mv /etc/nixos /etc/nixos.bak
```

Then run `rebuild` again to set up the mirror.

## Pre-commit issues

### Failures due to missing tools

Pre-commit hooks expect the devenv shell environment. Run them inside devenv:

```bash
devenv shell
pre-commit run --all-files
```

Outside devenv, hooks may fail with "command not found" because the pinned tool
versions aren't on PATH.

### Failures due to password manager

If pre-commit fails with an authentication error before running checks, the
secretspec preflight couldn't verify your password manager login.

```bash
op signin
```

See [Secrets Management](guides/secrets.md) for details.

## VS Code issues

### Hash mismatch on Marketplace extensions

When updating a pinned Marketplace extension, you may see a hash mismatch error.
This is expected — follow the update workflow:

1. Bump `mktplcRef.version`
2. Set `mktplcRef.hash` to a dummy SRI hash (`sha256-AAAA...`)
3. Build to get the mismatch error
4. Copy the `got: sha256-...` value into `mktplcRef.hash`
5. Build again

See [VS Code Extensions](reference/vscode-extensions.md) for the full guide.

!!! tip "Force evaluation"
    To surface Marketplace hash mismatches without a full system rebuild:
    ```bash
    nix build .#nixosConfigurations.<host>.config.system.build.toplevel
    ```

### Settings symlink not converted

If `~/.config/Code/User/settings.json` is still a read-only symlink after
rebuilding, the activation script may not have run. Try:

```bash
rm ~/.config/Code/User/settings.json
rebuild
```

See [VS Code Settings](reference/vscode-settings.md) for troubleshooting details.

## Git issues

### SSH signing key not found

> `fatal: either user.signingkey or gpg.ssh.defaultKeyCommand needs to be configured`

Generate a dedicated signing key:

```bash
ssh-keygen -t ed25519 -C "git-signing" -f ~/.ssh/id_ed25519_git_signing
```

Then add the public key to GitHub as a **Signing key** and configure it in
`home/modules/git.nix`. See [Git & GitHub](git-github.md#ssh-commit-signing)
for details.

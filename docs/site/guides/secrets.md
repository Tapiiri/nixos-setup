# Secrets Management

This repo uses [secretspec](https://github.com/juspay/secretspec) (via devenv)
to manage secrets declaratively. Secrets are fetched from a password manager at
development time.

## How it works

`devenv.nix` enables secretspec, which expects a password manager CLI to be
available and authenticated. If it isn't, devenv tasks can fail with opaque
errors.

The repo provides preflight scripts that check authentication **before** running
tasks, giving clear instructions when something is wrong.

## Password manager setup

This repo uses **1Password** (`op`) as the password manager backend.
Secretspec has native 1Password support — the provider is configured
automatically via `SECRETSPEC_PROVIDER=onepassword` in `devenv.nix`.

The `op` CLI is installed via the NixOS system modules
(`programs._1password.enable = true` in `configuration.nix`).

### Signing in

```bash
op signin
```

### Verifying authentication

```bash
scripts/ensure-password-manager-login echo "Authenticated!"
```

This runs the given command only if the password manager is authenticated.
If not, it prints instructions on how to fix it.

## Adding secrets

The `add-secret` script adds a secret to both secretspec and the password
manager in one step:

```bash
scripts/add-secret <secret-name>
```

It will:

1. Prompt for the secret value
2. Store it in the password manager
3. Add the reference to `secretspec.toml`

## Common issues

### devenv fails with opaque errors

If you see errors during `devenv shell` or `devenv tasks run ...` that mention
secrets or authentication:

```bash
op signin
```

Then retry the command.

### "password manager not available"

Make sure `op` is installed. In this repo it's provided via the NixOS system
module `programs._1password` in `configuration.nix`.

### Pre-commit hooks fail before running checks

The preflight script runs before the actual task. If it fails, you'll see a
message telling you to authenticate. Follow the instructions in the output.

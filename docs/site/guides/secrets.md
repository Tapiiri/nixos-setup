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

Currently the only implemented backend is **LastPass** (`lpass`). The code is
structured with a protocol-based abstraction so adding another backend later is
straightforward.

### Logging in

```bash
lpass login <your-email>
```

### Verifying authentication

```bash
scripts/ensure-password-manager-login echo "Authenticated!"
```

This runs the given command only if the password manager is authenticated.
If not, it prints instructions on how to fix it.

## The preflight flow

Pre-commit hooks that call `devenv tasks ...` run a small preflight first:

```text
pre-commit hook triggers
  ↓
scripts/ensure-password-manager-login
  ├─ authenticated? → continue to devenv task
  └─ not authenticated? → print fix instructions, exit 1
```

This prevents confusing failures deep in the devenv task chain.

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
lpass login <your-email>
```

Then retry the command.

### "password manager not available"

Make sure `lpass` (or your configured backend) is installed. In this repo it's
provided via Home Manager — see `home/modules/lastpass-cli.nix`.

### Pre-commit hooks fail before running checks

The preflight script runs before the actual task. If it fails, you'll see a
message telling you to authenticate. Follow the instructions in the output.

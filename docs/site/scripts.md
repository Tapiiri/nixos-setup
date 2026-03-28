# Scripts Overview

This repo ships user-facing CLI tools under `scripts/`, with Python
implementations in `scripts_py/` and unit tests in `tests/`.

## Design philosophy

Every script follows the **thin wrapper + testable implementation** pattern:

```text
scripts/rebuild          ← user runs this
  └─ scripts_py/cli/rebuild_dispatch.py  ← actual logic (testable)
```

The wrappers are intentionally thin — they bootstrap `sys.path` so the Python
module can be imported, then delegate immediately. This keeps scripts runnable
in minimal environments while allowing full test coverage of the implementations.

### The bootstrap snippet

Each wrapper in `scripts/` starts with a common pattern:

```python
#!/usr/bin/env python3
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from scripts_py.cli.some_module import main
main()
```

## Package structure

```text
scripts_py/
├── __init__.py          # Package root
├── utils.py             # Compat facade (re-exports from lib/ and repo/)
├── cli/                 # User-facing CLI implementations
│   ├── rebuild.py
│   ├── rebuild_dispatch.py
│   ├── setup_links.py
│   ├── sync_vscode_settings.py
│   ├── import_dotfiles.py
│   ├── add_secret.py
│   ├── audit_tooling.py
│   ├── cached_nix_check.py
│   ├── cached_pytest.py
│   ├── ensure_password_manager_login.py
│   ├── ensure_cachix_cache.py
│   ├── sync_github_labels.py
│   ├── setup_github_pages.py
│   ├── sync_schemastore_index.py
│   ├── validate_schemastore_schemas.py
│   └── update_github_env.py
├── ci/                  # CI automation helpers
│   ├── attest_ci_checks.py
│   ├── check_ci_attestation.py
│   └── ci_attestation_gate.py
├── lib/                 # Shared libraries (no repo-layout assumptions)
│   ├── utils.py
│   ├── depmap.py
│   ├── schemastore.py
│   ├── nix_check_attestation.py
│   ├── test_attestation.py
│   ├── tooling_audit.py
│   ├── tooling_discovery.py
│   └── password_manager.py
└── repo/                # Repo-context utilities
    └── context.py       # Repo root detection (RepoContext)
```

## Script inventory

### System management

| Script | Description | Details |
|--------|-------------|---------|
| `rebuild` | Dispatcher — selects remote vs local rebuild | [Rebuild guide](guides/rebuild.md) |
| `rebuild-inner` | Implementation — runs `nixos-rebuild switch` with mirror | [Rebuild guide](guides/rebuild.md) |
| `setup-links` | Symlink repo scripts + configs into user locations | [Below](#setup-links) |
| `import-dotfiles` | Import existing dotfiles into `dotfiles/` | [Below](#import-dotfiles) |

### VS Code

| Script | Description | Details |
|--------|-------------|---------|
| `sync-vscode-settings` | Capture runtime preferences into Nix | [VS Code Settings](reference/vscode-settings.md) |

### Development & CI

| Script | Description | Details |
|--------|-------------|---------|
| `attest-ci-checks` | Write CI attestation as git note | [CI & Attestation](guides/ci-attestation.md) |
| `check-ci-attestation` | Verify commit has attestation | [CI & Attestation](guides/ci-attestation.md) |
| `ci-attestation-gate` | GitHub Actions skip decision | [CI & Attestation](guides/ci-attestation.md) |
| `cached-nix-check` | `nix flake check` with attestation caching | [CI & Attestation](guides/ci-attestation.md) |
| `cached-pytest` | pytest with file-level caching | [CI & Attestation](guides/ci-attestation.md) |
| `audit-tooling` | Report tooling coverage per file type | — |

### Secrets & authentication

| Script | Description | Details |
|--------|-------------|---------|
| `add-secret` | Add secret to secretspec + password manager | [Secrets guide](guides/secrets.md) |
| `ensure-password-manager-login` | Preflight authentication check | [Secrets guide](guides/secrets.md) |

### GitHub & infrastructure

| Script | Description | Details |
|--------|-------------|---------|
| `sync-github-labels` | Sync labels from `.github/labels.yml` | [Git & GitHub](git-github.md) |
| `setup-github-pages` | Configure GitHub Pages (Actions source) | [Git & GitHub](git-github.md) |
| `update-github-env` | Update GitHub environment variables | [Git & GitHub](git-github.md) |
| `ensure-cachix-cache` | Ensure Cachix binary cache is configured | — |

### Schema management

| Script | Description |
|--------|-------------|
| `sync-schemastore-index` | Fetch SchemaStore catalog, match repo files, vendor schemas |
| `validate-schemastore-schemas` | Validate files against SchemaStore schemas |

## Script details

### `setup-links`

Creates symlinks from this repo to standard user locations:

- Links all scripts into `~/.local/bin`
- Links dotfiles from `dotfiles/home/` into `$HOME/`
- Can link host-specific Home Manager entrypoints (from `hosts/<hostname>/`) into `~/.config/home-manager/`

**Safety:**

- Refuses to modify **root-owned** targets (prints the manual command instead)
- Idempotent — if the symlink already points to the right place, it does nothing
- Creates parent directories as needed

```bash
./scripts/setup-links
```

### `import-dotfiles`

Bootstrap the repo from an existing machine by copying existing configs:

- `~/.<NAME>` → `dotfiles/home/<NAME>`
- `~/.config/<NAME>` → `dotfiles/config/<NAME>`

**Safety:**

- Does **not** overwrite existing paths in `dotfiles/`

```bash
./scripts/import-dotfiles
```

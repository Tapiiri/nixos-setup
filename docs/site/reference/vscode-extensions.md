# VS Code Extensions & Marketplace Packaging

This repo installs most VS Code extensions via `pkgs.vscode-extensions.*`.
That attribute set only contains extensions **packaged in nixpkgs**, so some
Marketplace extensions (like `openai.chatgpt`) may not exist there.

When an extension is missing from `pkgs.vscode-extensions`, use the Marketplace
fetch/build path from `pkgs.vscode-utils` instead.

## Using `buildVscodeMarketplaceExtension`

In `home/features/vscode/default.nix`, build a Nix derivation for a Marketplace
extension and include it in `programs.vscode.profiles.default.extensions`:

```nix
CodexExt = pkgs.vscode-utils.buildVscodeMarketplaceExtension {
  mktplcRef = {
    publisher = "openai";
    name = "chatgpt";
    version = "0.5.56";

    # IMPORTANT: the hash must be inside mktplcRef
    hash = "sha256-FAy2Cf2XnOnctBBATloXz8y4cLNHBoXAVnlw42CQzN8=";
  };
};
```

!!! warning "Hash placement"
    The fixed-output hash **must** be inside `mktplcRef`, not at the top level.
    In the nixpkgs snapshot this repo pins, the Marketplace helper converts
    `mktplcRef` into `fetchurl` arguments including `hash`. A top-level `hash`
    attribute is silently ignored, producing warnings like:

    > `warning: found empty hash, assuming 'sha256-AAAA…'`

## Updating pinned version + hash

Marketplace extensions change frequently. To update reproducibly:

1. Update `mktplcRef.version`
2. Set `mktplcRef.hash` to a dummy SRI hash (e.g. `sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=`)
3. Build once — you'll get a hash mismatch error
4. Copy the `got: sha256-...` value into `mktplcRef.hash`
5. Build again — should succeed

!!! tip "Force evaluation without full rebuild"
    ```bash
    nix build .#nixosConfigurations.<host>.config.system.build.toplevel
    ```

## Common gotchas

### Publisher casing matters

The Marketplace website is case-insensitive, but the VSIX download URL used by
`buildVscodeMarketplaceExtension` may be **case-sensitive**.

If you see `curl: (22) ... 404`, check the exact publisher casing:

```nix
# ✅ Correct
publisher = "1Password";

# ❌ 404 error
publisher = "1password";
```

### Don't guess the version

A wrong `mktplcRef.version` produces a 404 (the VSIX asset doesn't exist).

Get the correct version from the Marketplace page:

> `https://marketplace.visualstudio.com/items?itemName=PUBLISHER.EXTENSION_NAME`

Once the URL is valid, you'll see a **hash mismatch** (not a 404) — that's your
cue to pin the real hash.

### Dummy hash must be SRI-formatted

The placeholder must be an SRI hash like `sha256-AAAA...`. A raw hex string or
untyped fake will cause evaluation to fail before the fetch even happens.

## Notes

- This approach is fully declarative and works well with Home Manager's VS Code module
- If you prefer fewer rebuild failures on updates, you can keep some extensions
  installed manually via VS Code (mutable extensions dir), but you lose
  reproducibility

## Related

- [VS Code Settings](vscode-settings.md) — the hybrid settings merge workflow
- [Architecture](../architecture.md) — where VS Code feature files live

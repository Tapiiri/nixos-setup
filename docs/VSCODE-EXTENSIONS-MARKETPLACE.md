# VS Code extensions from the Marketplace (when nixpkgs doesn’t have them)

This repo installs most VS Code extensions via `pkgs.vscode-extensions.*`.
That attribute set only contains extensions that are **packaged in nixpkgs**, so some Marketplace extensions (like `openai.chatgpt`) may not exist there.

When an extension is missing from `pkgs.vscode-extensions`, use the Marketplace fetch/build path from `pkgs.vscode-utils` instead.

## ✅ Recommended approach: `buildVscodeMarketplaceExtension`

In `home/features/vscode/default.nix` we can build a Nix derivation for a Marketplace extension and then include it in:

- `programs.vscode.profiles.default.extensions = [ … ]`

Example (OpenAI Codex / ChatGPT extension):

- extension id: `openai.chatgpt`
- publisher: `openai`
- name: `chatgpt`

```nix
CodexExt = pkgs.vscode-utils.buildVscodeMarketplaceExtension {
  mktplcRef = {
    publisher = "openai";
    name = "chatgpt";
    version = "0.5.56";

    # IMPORTANT (for this repo’s nixpkgs pin):
    # the fixed-output hash must be inside `mktplcRef`.
    hash = "sha256-FAy2Cf2XnOnctBBATloXz8y4cLNHBoXAVnlw42CQzN8=";
  };
};
```

### Why is the hash inside `mktplcRef`?

In the nixpkgs snapshot pinned by this repo, the Marketplace helper converts `mktplcRef` into `fetchurl` arguments (including `hash`/`sha256`).
It does **not** forward a top-level `hash` attribute when calling `fetchurl`.

So if you put `hash = …;` at the top level, Nix will behave like the hash is missing and you’ll see warnings like:

- `warning: found empty hash, assuming 'sha256-AAAA…'`

## Updating pinned version + hash

Marketplace extensions change frequently; to update them reproducibly, bump both:

1. `mktplcRef.version`
2. `mktplcRef.hash`

Workflow:

1. Update `version`.
2. Temporarily set `hash` to `lib.fakeSha256` (or an obviously-wrong SRI hash).
3. Build once to get a hash mismatch error.
4. Copy the `got: sha256-…` value into `mktplcRef.hash`.
5. Build again.

## Notes

- This approach is fully declarative and works well with Home Manager’s VS Code module.
- If you prefer fewer rebuild failures on updates, you can also keep some extensions installed manually via VS Code (mutable extensions dir), but then you lose reproducibility.

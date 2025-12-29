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
2. Temporarily set `hash` to an obviously-wrong SRI hash.
3. Build once to get a hash mismatch error.
4. Copy the `got: sha256-…` value into `mktplcRef.hash`.
5. Build again.

### Common gotchas (learned the hard way)

#### 1) Publisher casing can matter

The Marketplace “item name” looks case-insensitive on the public website (e.g.
`1Password.op-vscode` loads fine), but the actual VSIX download URL used by
`buildVscodeMarketplaceExtension` may be **case-sensitive**.

If you see `curl: (22) ... 404`, double-check the exact publisher casing.
Example that required casing:

- ✅ `publisher = "1Password";`
- ❌ `publisher = "1password";` (404)

#### 2) Don’t guess the version

A wrong `mktplcRef.version` can also produce a 404 (because the VSIX asset for
that version doesn’t exist).

If you’re not sure what version to pin, get it from the Marketplace page:

- Open: <https://marketplace.visualstudio.com/items?itemName=PUBLISHER.EXTENSION_NAME>
- Use the version shown there (or scrape it) as the initial `mktplcRef.version`.

Once the URL is valid, you should see a **hash mismatch** (not a 404), which is
your cue that you’re now ready to pin the real `got: sha256-...` value.

#### 3) The dummy hash must be SRI-formatted

The placeholder hash must be an SRI hash like `sha256-AAAA...`.
If you use a raw hex string or an untyped fake, evaluation can fail before the
fetch even happens.

## Notes

- This approach is fully declarative and works well with Home Manager’s VS Code module.
- If you prefer fewer rebuild failures on updates, you can also keep some extensions installed manually via VS Code (mutable extensions dir), but then you lose reproducibility.

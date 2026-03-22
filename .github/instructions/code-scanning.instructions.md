---
applyTo: "**"
---

# Code Scanning alerts skill

This instruction teaches you how to fetch, interpret, triage, and fix GitHub
Code Scanning alerts for this repository using the `gh` CLI.

## Prerequisites

- The `gh` CLI is available in the devenv shell and assumed authenticated.
- The repository is `Tapiiri/nixos-setup`.

## Fetching alerts

### List all open alerts (summary)

```bash
gh api 'repos/Tapiiri/nixos-setup/code-scanning/alerts?state=open&per_page=100' \
  --jq '.[] | "#\(.number) [\(.rule.severity)] \(.tool.name)/\(.rule.id) — \(.most_recent_instance.location.path // "repo-level"):\(.most_recent_instance.location.start_line // "-")"'
```

### List alerts filtered by state

Valid `state` values: `open`, `dismissed`, `fixed`.

```bash
gh api 'repos/Tapiiri/nixos-setup/code-scanning/alerts?state=dismissed&per_page=100' \
  --jq '.[] | "#\(.number) \(.rule.description) — dismissed: \(.dismissed_reason)"'
```

### Get full detail for a single alert

```bash
gh api 'repos/Tapiiri/nixos-setup/code-scanning/alerts/{number}' \
  --jq '{number, state, tool: .tool.name, rule: .rule.id, severity: .rule.severity, description: .rule.description, file: .most_recent_instance.location.path, line: .most_recent_instance.location.start_line, message: .most_recent_instance.message.text, url: .html_url}'
```

### List all instances of an alert

```bash
gh api 'repos/Tapiiri/nixos-setup/code-scanning/alerts/{number}/instances' \
  --jq '.[] | {ref: .ref, state: .state, file: .location.path, line: .location.start_line, message: .message.text}'
```

### Group open alerts by rule

```bash
gh api 'repos/Tapiiri/nixos-setup/code-scanning/alerts?state=open&per_page=100' \
  --jq 'group_by(.rule.id) | .[] | {rule: .[0].rule.id, tool: .[0].tool.name, count: length, alerts: [.[].number]}'
```

### Get a rich description (for CodeQL / tools that provide help text)

```bash
gh api 'repos/Tapiiri/nixos-setup/code-scanning/alerts/{number}' \
  --jq '{rule_id: .rule.id, full_description: .rule.full_description, help: .rule.help, help_uri: .rule.help_uri}'
```

## Interpreting alert JSON

Key fields in the alert response:

| Field | Meaning |
|---|---|
| `.rule.id` | Machine identifier for the check (e.g. `PinnedDependenciesID`) |
| `.rule.severity` | `error`, `warning`, `note` |
| `.rule.description` | Short human-readable title |
| `.rule.full_description` | Detailed explanation (CodeQL provides this; Scorecard may not) |
| `.rule.help` | Markdown remediation guidance (when available) |
| `.tool.name` | Scanner that produced the finding (`Scorecard`, `CodeQL`, etc.) |
| `.most_recent_instance.location.path` | Affected file |
| `.most_recent_instance.location.start_line` | Line number |
| `.most_recent_instance.message.text` | Instance-level explanation |
| `.state` | `open`, `dismissed`, `fixed` |
| `.dismissed_reason` | `false positive`, `won't fix`, `used in tests`, or `null` |

## Triaging / dismissing alerts

### Dismiss a single alert

```bash
gh api -X PATCH 'repos/Tapiiri/nixos-setup/code-scanning/alerts/{number}' \
  -f state=dismissed \
  -f dismissed_reason='won'\''t fix' \
  -f dismissed_comment='Reason for dismissal'
```

Valid `dismissed_reason` values:
- `false positive` — the finding is incorrect
- `won't fix` — accepted risk or not applicable
- `used in tests` — the flagged code is test-only

**Always provide a `dismissed_comment`** explaining the rationale.

### Re-open a dismissed alert

```bash
gh api -X PATCH 'repos/Tapiiri/nixos-setup/code-scanning/alerts/{number}' \
  -f state=open
```

## Fix patterns by tool

### OSSF Scorecard (`tool.name == "Scorecard"`)

Scorecard alerts come from `.github/workflows/scorecard.yml`, which runs the
OSSF Scorecard analysis and uploads SARIF results to code scanning.

#### PinnedDependenciesID — pin GitHub Actions to commit SHAs

**Problem**: `uses:` references use a mutable tag (e.g. `@v4`) instead of an
immutable commit SHA.

**Fix**: Replace the tag with the full 40-character commit SHA, adding a
trailing comment with the version for readability.

Before:
```yaml
- uses: actions/checkout@v4
```

After:
```yaml
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
```

To find the SHA for a given tag:
```bash
gh api 'repos/{owner}/{action-repo}/git/ref/tags/{tag}' --jq '.object.sha'
# If the tag is annotated (returns "tag" type), dereference it:
gh api 'repos/{owner}/{action-repo}/git/ref/tags/{tag}' --jq '.object' \
  | jq -r 'if .type == "tag" then .url else .sha end' \
  | xargs -I{} gh api {} --jq '.object.sha // .sha'
```

Or more simply, check the action's releases page on GitHub for the commit SHA.

**Affected files in this repo** (check current alerts for the exact lines):
- `.github/workflows/ci.yml`
- `.github/workflows/update-flake-lock.yml`
- `.github/workflows/docs.yml`
- `.github/workflows/scorecard.yml`

Note: `scorecard.yml` already pins most actions to SHAs. The others use tags.

#### TokenPermissionsID — restrict workflow token permissions

**Problem**: A workflow or job does not declare explicit `permissions`, so the
`GITHUB_TOKEN` gets broad default access.

**Fix**: Add a top-level `permissions: read-all` or `permissions: {}` block,
then grant minimum required permissions per-job.

Example:
```yaml
# Top of workflow — restrictive default
permissions: read-all

jobs:
  build:
    permissions:
      contents: read
    # ...
```

Common per-job permissions:
- `contents: read` — for checkout
- `contents: write` — for pushing commits / creating releases
- `pull-requests: write` — for creating or commenting on PRs
- `security-events: write` — for uploading SARIF
- `id-token: write` — for OIDC / Sigstore

Reference: <https://docs.github.com/en/actions/security-for-github-actions/security-guides/automatic-token-authentication#permissions-for-the-github_token>

**Affected files in this repo**:
- `.github/workflows/ci.yml` — missing top-level `permissions` block
- `.github/workflows/update-flake-lock.yml` — job-level permissions present
  but Scorecard still flags the workflow-level default

#### Security-Policy — add SECURITY.md

**Fix**: Create a `SECURITY.md` at the repository root describing how to report
vulnerabilities. A minimal template:

```markdown
# Security Policy

## Reporting a Vulnerability

If you discover a security issue, please report it by opening a
[private vulnerability report](https://github.com/Tapiiri/nixos-setup/security/advisories/new)
on this repository.

Do **not** open a public issue for security vulnerabilities.
```

#### License — add LICENSE

**Fix**: Create a `LICENSE` file at the repository root. Choose a license
appropriate for the project (e.g. MIT, GPL-3.0, etc.).

#### CII-Best-Practices / Fuzzing

These are repo-maturity indicators rather than code-level fixes:
- **CII-Best-Practices**: Requires enrolling the project in the
  [OpenSSF Best Practices Badge](https://www.bestpractices.dev/) program.
- **Fuzzing**: Requires setting up fuzz testing (e.g. via OSS-Fuzz).

For a personal NixOS config repo, these are typically triaged as `won't fix`:

```bash
gh api -X PATCH 'repos/Tapiiri/nixos-setup/code-scanning/alerts/{number}' \
  -f state=dismissed \
  -f dismissed_reason='won'\''t fix' \
  -f dismissed_comment='Not applicable for a personal NixOS configuration repository'
```

### CodeQL / generic SARIF tools

For tools that produce source-level findings (CodeQL, Semgrep, etc.):

1. **Read the alert detail** — use the single-alert query above. The
   `rule.full_description` and `rule.help` fields contain remediation guidance.
2. **Navigate to the source** — `location.path` and `location.start_line` point
   to the exact code.
3. **Check classifications** — alerts with `classifications: ["test"]` are
   flagged in test files; consider dismissing as `used in tests` if acceptable.
4. **Propose a targeted fix** — read the affected file context around the
   flagged line and apply the remediation suggested by the rule's help text.

## Current state of code scanning in this repo

- **Scanner**: OSSF Scorecard via `.github/workflows/scorecard.yml`
  (runs on push to `main`, weekly schedule, and branch protection rule events).
- **Upload**: SARIF results are uploaded to GitHub code scanning via
  `github/codeql-action/upload-sarif@v4`.
- **No CodeQL workflow** exists yet. If one is added in the future, this skill's
  CodeQL section applies.
- All current open alerts are from Scorecard (mostly `PinnedDependenciesID` and
  `TokenPermissionsID`).

---
name: scan
description: Fetch, triage, and fix GitHub code scanning alerts (OSSF Scorecard, CodeQL) for this repo using the gh CLI. Use when asked to check security alerts, code scanning findings, Scorecard results, or pinned dependency issues.
allowed-tools: Bash, Read, Edit, Write, Grep
---

Fetch and address code scanning alerts for this repo. The authoritative fix patterns are in `.github/instructions/code-scanning.instructions.md` — read it if you need detail beyond what's here.

## Step 1: Fetch current open alerts

!`gh api 'repos/Tapiiri/nixos-setup/code-scanning/alerts?state=open&per_page=100' --jq '.[] | "#\(.number) [\(.rule.severity)] \(.tool.name)/\(.rule.id) — \(.most_recent_instance.location.path // "repo-level"):\(.most_recent_instance.location.start_line // "-")"' 2>/dev/null || echo "gh CLI not available or not authenticated — run 'gh auth status' to check"`

## Step 2: Group by rule

```bash
gh api 'repos/Tapiiri/nixos-setup/code-scanning/alerts?state=open&per_page=100' \
  --jq 'group_by(.rule.id) | .[] | {rule: .[0].rule.id, tool: .[0].tool.name, severity: .[0].rule.severity, count: length, alerts: [.[].number]}'
```

Prioritise by severity: `error` → `warning` → `note`.

## Step 3: Get full detail on alerts to address

For each alert worth fixing or triaging:

```bash
gh api 'repos/Tapiiri/nixos-setup/code-scanning/alerts/{number}' \
  --jq '{number, state, tool: .tool.name, rule: .rule.id, severity: .rule.severity, description: .rule.description, file: .most_recent_instance.location.path, line: .most_recent_instance.location.start_line, message: .most_recent_instance.message.text, help: .rule.help}'
```

## Step 4: Apply fixes

**PinnedDependenciesID** — Pin GitHub Actions `uses:` from `@tag` to a full 40-char commit SHA:

Resolve the SHA:
```bash
# For lightweight tags:
gh api 'repos/{owner}/{action-repo}/git/ref/tags/{tag}' --jq '.object.sha'

# For annotated tags (dereference):
gh api 'repos/{owner}/{action-repo}/git/refs/tags/{tag}' --jq '.object' \
  | jq -r 'if .type == "tag" then .url else .sha end' \
  | xargs -I{} gh api {} --jq '.object.sha // .sha'
```

Then edit the workflow file:
```yaml
# Before:
- uses: actions/checkout@v4
# After:
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
```

**TokenPermissionsID** — Add explicit permissions to the workflow:
```yaml
permissions: read-all   # top-level restrictive default

jobs:
  my-job:
    permissions:
      contents: read    # minimum required
```

**Security-Policy** — Create `SECURITY.md` at repo root describing how to report vulnerabilities privately.

**CII-Best-Practices / Fuzzing** — Dismiss as `won't fix` (not applicable for a personal config repo):
```bash
gh api -X PATCH 'repos/Tapiiri/nixos-setup/code-scanning/alerts/{number}' \
  -f state=dismissed \
  -f dismissed_reason="won't fix" \
  -f dismissed_comment='Not applicable for a personal NixOS configuration repository'
```

**Any dismissal** must include a `dismissed_comment` explaining the rationale. Valid reasons: `false positive`, `won't fix`, `used in tests`.

## Step 5: Re-run check:all after file changes

After editing any workflow or repo files:

```bash
devenv tasks run -m all check:all
```

The `actionlint` and `yamllint` checks will verify the edited workflows are still valid.

## Step 6: Report

Summarise:
- Alerts fixed (what changed)
- Alerts dismissed (what and why)
- Remaining open alerts and their status

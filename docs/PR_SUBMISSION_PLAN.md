# PR Submission Plan — Claude Code User Hook Extensibility
## Ordered Steps from Zero to Filed

*Authors: Mark Menkhus and Claude Sonnet 4.6*
*Filed: April 2026*

---

## Reality Check First

Before any steps, know what kind of project this is:

**License:** "© Anthropic PBC. All rights reserved."
This is NOT open source. There is no Apache, MIT, or GPL license here.

**What this means for contributions:**
- External code PRs to the core `cli.js` are not the contribution model
- The source code for Claude Code is not in this repo — `cli.js` is a compiled
  artifact, not editable source
- Merged PRs from external contributors are docs and examples only
- The correct path for a design proposal is a **Feature Request Issue**,
  not a code PR

**What we CAN file:**
1. A well-formed Feature Request Issue with the full design document
2. A companion docs/examples PR showing the pattern in action (optional)
3. A reference implementation in our own public repo that Anthropic can adopt

**The IPR/CLA question:**
Filing a GitHub issue requires no CLA — you're just talking to them.
If Anthropic's engineering team likes the design and invites a code PR,
THAT is when CLA/IPR becomes a blocking question. Cross that bridge then.

---

## Phase 1 — Verify Your GitHub Setup

These steps confirm you have the tools and access needed. Do these once,
from a terminal, before anything else.

### Step 1.1 — Confirm gh CLI is authenticated

```sh
gh auth status
```

Expected output: `Logged in to github.com as menkhus`

If not logged in:
```sh
gh auth login
# Choose: GitHub.com → HTTPS → Login with a web browser
# Follow the prompts — it opens a browser for OAuth
```

### Step 1.2 — Confirm your identity on GitHub

```sh
gh api user --jq '{login: .login, name: .name, email: .email}'
```

Should show `menkhus` and your name. This is what will appear on the issue.

### Step 1.3 — Confirm you can see the repo

```sh
gh repo view anthropics/claude-code --json name,description | python3 -m json.tool
```

If this returns the repo description, you have read access. Good.

### Step 1.4 — Check if you've previously interacted with the repo

```sh
gh issue list --repo anthropics/claude-code --author menkhus 2>/dev/null
gh pr list --repo anthropics/claude-code --author menkhus 2>/dev/null
```

Know your history before filing. If you've filed similar requests before,
reference them in the new issue.

---

## Phase 2 — Prepare the Submission Package

The issue needs three things: a clear problem statement, the design document,
and a reference implementation. All three exist — this phase gets them ready.

### Step 2.1 — Make the design document publicly accessible

The design doc lives at:
`~/Documents/src/claude_code_management_scripts/docs/USER_HOOKS_EXTENSIBILITY_DESIGN.md`

Options (pick one):
- **Push the repo to GitHub** — `gh repo create menkhus/claude_code_management_scripts --public`
  then `git push`. The design doc is then linkable at a stable URL.
- **Gist** — `gh gist create docs/USER_HOOKS_EXTENSIBILITY_DESIGN.md --public`
  Returns a URL you can paste into the issue.

Recommendation: push the full repo. The reference implementation (cleanup hook,
startup audit, autoground) gives Anthropic something concrete to look at.
A gist is fine if you want to keep the repo private for now.

### Step 2.2 — Review the design doc one more time

```sh
cat ~/Documents/src/claude_code_management_scripts/docs/USER_HOOKS_EXTENSIBILITY_DESIGN.md
```

Read it as an Anthropic engineer would. Ask:
- Is the problem statement concrete and verifiable?
- Is the prior art section persuasive (it is — the Unix table is good)?
- Are the requirements specific enough to implement?
- Is the security model complete?
- Does the migration path show backward compatibility?

Fix anything that reads like a TODO or placeholder.

### Step 2.3 — Confirm reference implementation scripts are clean

The scripts that ship as examples:
```sh
cat ~/Documents/src/claude_code_management_scripts/hooks/claude-settings-cleanup.sh
cat ~/Documents/src/claude_code_management_scripts/hooks/claude-startup-audit.py
```

These are the evidence that the design works in practice. They should be
production quality — they already are, but verify.

---

## Phase 3 — File the Feature Request Issue

Anthropic has a feature request template. We use it. Don't file a raw issue —
the template is how their triage team processes incoming requests.

### Step 3.1 — Understand the template fields

Their feature request template (`feature_request.yml`) requires:
- **Problem Statement** — what problem, not what solution
- **Proposed Solution** — concrete, specific UX description
- **Alternative Solutions** — what you tried, what exists
- **Priority** — Critical / High / Medium / Low
- **Feature Category** — Configuration and settings
- **Use Case Example** — step-by-step scenario
- **Additional Context** — link to design doc here

### Step 3.2 — Draft the issue body offline first

Write it here before filing. Filing directly in gh is harder to review.

Create a draft:
```sh
cat > /tmp/hooks-issue-draft.md << 'DRAFT'
[paste the filled-out template here]
DRAFT
```

**Problem Statement draft:**
```
Claude Code's hook system has no safe, upgrade-proof home for user-supplied
scripts. Users must invent their own paths (~/.claude/scripts/,
~/.claude/user_hook_scripts/, etc.) that Claude Code does not document,
reserve, or protect. These paths can be overwritten, renamed, or disappear
on any upgrade. There is no discovery mechanism, no permission enforcement,
and no identity logging for user-supplied hooks. Users who have invested in
hooks for security, auditing, and session continuity have no foundation they
can rely on across upgrades or machines.
```

**Proposed Solution draft:**
```
Introduce ~/.claude/hooks.d/ as a reserved, upgrade-safe drop-in directory
for user hook descriptors, following the Unix .d/ convention (cron.d/,
sudoers.d/, systemd drop-ins). Claude Code searches this directory at
startup, loads JSON descriptors it finds there, and merges them with
hooks registered in settings.json. The directory is guaranteed never
touched by Claude Code upgrades. Each descriptor identifies its author,
version, event, command, and timeout. Permission enforcement follows
cron/sudo: wrong owner or world-writable = logged and skipped.
Full design at: [link to design doc]
```

### Step 3.3 — File the issue

```sh
cd ~/Documents/src/claude_code_management_scripts

gh issue create \
  --repo anthropics/claude-code \
  --title "[FEATURE] ~/.claude/hooks.d/ — upgrade-safe drop-in directory for user hook scripts" \
  --label "enhancement" \
  --body "$(cat /tmp/hooks-issue-draft.md)"
```

`gh` will open your default editor if `--body` is omitted — that also works.

After filing, `gh` prints the issue URL. Save it.

### Step 3.4 — Attach the design document link

Edit the issue after filing to ensure the design doc URL is prominent:

```sh
gh issue edit <NUMBER> --repo anthropics/claude-code \
  --body-file /tmp/hooks-issue-draft.md
```

Or just comment on it:
```sh
gh issue comment <NUMBER> --repo anthropics/claude-code \
  --body "Full design document with requirements, security model, load algorithm, and reference implementation: <URL>"
```

---

## Phase 4 — Tag It Correctly and Monitor

### Step 4.1 — Verify labels after filing

```sh
gh issue view <NUMBER> --repo anthropics/claude-code --json labels
```

Should show `enhancement`. If not, Anthropic's triage bot will add labels
within hours — their `claude-issue-triage.yml` workflow runs automatically.

### Step 4.2 — Watch for the triage response

Anthropic's triage workflow uses Claude to label and respond to issues.
Within 24 hours you will typically get:
- Automatic labels (feature category, area)
- Possibly a triage comment asking for clarification

Check:
```sh
gh issue view <NUMBER> --repo anthropics/claude-code --comments
```

### Step 4.3 — Respond to any triage questions promptly

If they ask "can you show a concrete example?", the reference implementation
is the answer. Link to the repo or paste the hook descriptor JSON.

---

## Phase 5 — If They Invite a Code Contribution

This phase only applies if an Anthropic engineer responds with interest in
a code PR. Do not proceed here speculatively.

### Step 5.1 — Ask explicitly about CLA/IPR requirements

Post a comment on the issue:
```
Before preparing a code PR, I want to confirm the contribution process.
Does Anthropic require a CLA or contributor agreement for external code
contributions? I want to make sure IPR is handled correctly before
submitting anything.
```

Wait for a clear answer. Do not fork and file a code PR before this is
answered.

### Step 5.2 — If a CLA is required

Anthropic may use:
- **CLA Assistant** (GitHub bot) — it will comment on your PR and ask you
  to sign via a web link. Click it, read it, sign it with your GitHub account.
- **Manual email agreement** — less common but possible for a proprietary project
- **No CLA required** — also possible; they may accept contributions under their
  existing license terms

In any case: read the agreement before signing. Key questions:
- Do you retain any rights to the contributed code?
- What license does your contribution go under?
- Does the agreement cover AI-assisted work? (Novel question — ask if unclear)

### Step 5.3 — Fork and prepare the code PR

```sh
# Fork the repo
gh repo fork anthropics/claude-code --clone

# Create a branch
cd claude-code
git checkout -b menkhus/user-hooks-extensibility

# Make the changes specified in the design doc (§12 Code Changes Required)
# ... implement loadHooksFromDropInDirectories(), validateHookDescriptor(), etc.

# File the PR
gh pr create \
  --repo anthropics/claude-code \
  --title "feat: ~/.claude/hooks.d/ drop-in directory for user hook scripts" \
  --body "$(cat /tmp/pr-body.md)"
```

The PR body should reference the original issue number and the design doc.

---

## Phase 6 — Parallel Track: Our Own Reference Implementation

Regardless of what Anthropic does with the issue, maintain the reference
implementation in `claude_code_management_scripts`. It demonstrates the
pattern works, documents the value, and gives other Claude Code users
something to use today — without waiting for upstream.

### Current state

```
hooks/
    claude-settings-cleanup.sh     DONE — clears permissions.allow on Stop
    claude-startup-audit.py        DONE — audits CLAUDE.md chain on SessionStart
~/.claude/scripts/
    autoground.py                  DONE — substrate DB grounding on Stop
    context-stop.py                DONE — context size warning
    context-status.py              DONE — status bar token %
```

### What remains for the reference implementation

- [ ] Write `install.sh` — symlinks hooks into `~/.claude/user_scripts/`,
      patches `~/.claude/settings.json` with absolute paths, uses `$HOME`
      not hardcoded `/Users/mark`
- [ ] Write `hooks.d/` descriptor JSON files for each existing hook
      (demonstrates the proposed format even before upstream ships it)
- [ ] Write `docs/examples/` showing a minimal complete hook from scratch
- [ ] Push the repo public: `gh repo create menkhus/claude_code_management_scripts --public --push`

---

## Summary — Ordered Checklist

```
Phase 1 — Setup (do once)
  [ ] gh auth status — confirm logged in as menkhus
  [ ] gh api user — confirm identity
  [ ] gh repo view anthropics/claude-code — confirm access

Phase 2 — Package
  [ ] Push or gist the design doc — get a public URL
  [ ] Review design doc as an outside reader
  [ ] Verify cleanup + audit scripts are production quality

Phase 3 — File
  [ ] Draft issue body in /tmp/hooks-issue-draft.md
  [ ] gh issue create with feature_request template fields
  [ ] Save the issue number and URL
  [ ] Comment with design doc URL

Phase 4 — Monitor
  [ ] Watch for triage labels (24h)
  [ ] Respond to any clarification requests

Phase 5 — Code PR (ONLY if invited)
  [ ] Ask about CLA/IPR requirements explicitly
  [ ] Read and sign CLA if required
  [ ] Confirm AI-assisted work is acceptable under their terms
  [ ] gh repo fork → branch → implement → gh pr create

Phase 6 — Reference implementation (parallel, independent)
  [ ] Write install.sh
  [ ] Write hooks.d/ descriptor JSON files
  [ ] Push repo public
```

---

## Key Contacts / References

- Repo: https://github.com/anthropics/claude-code
- Issues: https://github.com/anthropics/claude-code/issues
- Feature request template: `.github/ISSUE_TEMPLATE/feature_request.yml`
- Design doc: `~/Documents/src/claude_code_management_scripts/docs/USER_HOOKS_EXTENSIBILITY_DESIGN.md`
- Reference impl: `~/Documents/src/claude_code_management_scripts/hooks/`

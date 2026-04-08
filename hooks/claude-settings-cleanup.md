# claude-settings-cleanup — Installation & Reference

Clears `permissions.allow` from `.claude/settings.local.json` at the end of
every Claude Code session. Prevents credential leakage and stale permission
accumulation.

## Why this exists

Claude Code persists every tool-call permission you approve into
`.claude/settings.local.json`. Over time this accumulates:

- **Hardcoded API keys** — e.g. `export ANTHROPIC_API_KEY="sk-ant-..."` captured
  as a one-shot bash approval
- **One-shot literal commands** — temp paths, multi-line blobs, inline curl calls
- **Wildcard permissions** that weren't intentional and persist forever

The `permissions.allow` list is rebuilt interactively each session. Clearing it
on exit is safe — you'll be asked to approve things again next time, which is
the intended security model.

## What is cleared vs. kept

| Field | Action |
|---|---|
| `permissions.allow` | **Cleared** (set to `[]`) |
| `permissions.deny` | Kept (intentional explicit denials) |
| `enableAllProjectMcpServers` | Kept |
| `enabledMcpjsonServers` | Kept |
| All other keys | Kept |

## Files

- **Script:** `~/.claude/user_hook_scripts/claude-settings-cleanup.sh`
- **Docs:** `~/.claude/user_hook_scripts/claude-settings-cleanup.md` (this file)
- **Global hook:** `~/.claude/settings.json` (Stop hook)
- **Global gitignore:** `~/.gitignore_global` (prevents ever committing the file)

## Installing on a new machine

### 1. Copy the hook scripts directory

```sh
mkdir -p ~/.claude/user_hook_scripts
cp claude-settings-cleanup.sh ~/.claude/user_hook_scripts/
cp claude-settings-cleanup.md ~/.claude/user_hook_scripts/
chmod +x ~/.claude/user_hook_scripts/claude-settings-cleanup.sh
```

Or sync from your dotfiles repo — `~/.claude/user_hook_scripts/` is the right
home for all Claude Code hooks you own.

**Dependency:** `jq` must be installed.

```sh
brew install jq   # macOS
apt install jq    # Debian/Ubuntu
```

### 2. Add the Stop hook to `~/.claude/settings.json`

Merge this into your existing `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "/Users/YOUR_USERNAME/.claude/user_hook_scripts/claude-settings-cleanup.sh"
          }
        ]
      }
    ]
  }
}
```

**Important:** Use an absolute path — Claude Code does not expand `~` in hook
commands on all platforms.

The global `~/.claude/settings.json` hook fires for **every project** — no
per-project setup needed.

### 3. Protect against accidental git commits

Add to `~/.gitignore_global`:

```
.claude/settings.local.json
```

Configure git to use it:

```sh
git config --global core.excludesfile ~/.gitignore_global
```

### 4. (Optional) Clean the global settings.local.json too

The Stop hook runs in project context, so `~/.claude/settings.local.json` is
not automatically cleaned. To include it, add a second hook entry:

```json
{
  "type": "command",
  "command": "/Users/YOUR_USERNAME/.claude/user_hook_scripts/claude-settings-cleanup.sh /Users/YOUR_USERNAME/.claude/settings.local.json"
}
```

## Running manually

```sh
# Clean current project
~/.claude/user_hook_scripts/claude-settings-cleanup.sh

# Clean a specific file
~/.claude/user_hook_scripts/claude-settings-cleanup.sh /path/to/.claude/settings.local.json

# Bulk clean all projects
find ~/Documents/src ~/src ~/writing -name "settings.local.json" -path "*/.claude/*" 2>/dev/null \
  | while read -r f; do ~/.claude/user_hook_scripts/claude-settings-cleanup.sh "$f"; done
```

## Verifying the hook is active

```sh
# Check the hook is registered
cat ~/.claude/settings.json | jq '.hooks'

# Confirm the script is executable
ls -la ~/.claude/user_hook_scripts/claude-settings-cleanup.sh

# Dry-run: copy a settings file and clean the copy
cp .claude/settings.local.json /tmp/test-settings.json
~/.claude/user_hook_scripts/claude-settings-cleanup.sh /tmp/test-settings.json
cat /tmp/test-settings.json
```

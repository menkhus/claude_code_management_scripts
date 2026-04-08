# settings.local.json — The Credential Leakage Problem

## What It Is

`.claude/settings.local.json` is Claude Code's per-project permission store.
Every time you approve a tool call, it can be persisted here. The file is
created automatically and grows silently.

## The Risk

Claude Code records approved bash commands verbatim. If you ran:

```sh
export ANTHROPIC_API_KEY="sk-ant-api03-..."
```

...and approved it, the full string — including the key value — was written
into `settings.local.json`. It sits there across all future sessions, readable
by anything with filesystem access.

**This happened.** In the aifilter-project, a live API key was found persisted
in `settings.local.json` on 2026-04-07. The key had been there since late 2024.

## Why It Happens

When Claude suggests a command and you approve it with option #2 ("allow for
this project"), Claude Code writes the exact command string into the allow list.
There is no secrets detection, no expiry, and no cleanup mechanism.

## The Remediation

### Immediate (done 2026-04-07)
1. Found and cleared 69 `settings.local.json` files across all projects
2. Rotated the exposed API key at console.anthropic.com (TODO: verify done)
3. Installed exit hook to clear `permissions.allow` on every session end

### Ongoing (automated)
Exit hook: `~/.claude/user_hook_scripts/claude-settings-cleanup.sh`
- Fires on the Stop event via `~/.claude/settings.json`
- Clears `permissions.allow` entirely (set to `[]`)
- Preserves `permissions.deny`, MCP config, and all other keys
- Runs silently; logs to stderr

### Structural (ongoing)
`~/.gitignore_global` excludes `.claude/settings.local.json`
- Prevents accidental commits in any repo on this machine
- Set via: `git config --global core.excludesfile ~/.gitignore_global`

## What Is Preserved

The exit hook does NOT clear:
- `permissions.deny` — explicit denials are intentional
- `enableAllProjectMcpServers` — MCP server config
- `enabledMcpjsonServers` — MCP server list
- Any other keys

## Transferring to a New Machine

1. Copy `~/.claude/user_hook_scripts/claude-settings-cleanup.sh`
2. Register Stop hook in `~/.claude/settings.json`
3. Add `.claude/settings.local.json` to `~/.gitignore_global`

See `hooks/claude-settings-cleanup.md` for full instructions.

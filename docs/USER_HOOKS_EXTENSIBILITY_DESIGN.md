# User Hook Extensibility for Claude Code
## Design Guide for a Production PR

*Authors: Mark Menkhus and Claude (Anthropic)*
*Filed: April 2026*
*Scope: Code + documentation + tests PR to anthropics/claude-code*

*This design was developed collaboratively: Mark Menkhus (20+ months of
Claude Code production use across 60+ projects, prior systems programming
experience on OSF/1 and HP-UX) and Claude Sonnet 4.6 (design synthesis,
prior art research, document authorship). The PR will be submitted by
Mark Menkhus (github.com/menkhus). Both authors are credited here.*

---

## 1. Problem Statement

Claude Code's hook system is powerful but has no safe, stable, upgrade-proof
home for user-supplied scripts. The current situation:

- Hook commands in `~/.claude/settings.json` point to absolute paths the user
  invents (`~/.claude/scripts/`, `~/.claude/user_hook_scripts/`, etc.)
- None of these paths are documented, reserved, or protected by Claude Code
- Claude Code upgrades may create, rename, or reorganize `~/.claude/` contents
- Users on multiple machines must manually recreate the same paths
- There is no discovery mechanism — every hook must be manually registered in
  `settings.json`
- There is no load-order contract, no permission enforcement, no identity
  logging for user-supplied hooks
- Enterprise/admin deployments have no way to push hooks to all users

The consequence: users doing exactly the right thing (extending Claude Code via
hooks) are doing so on an unstable foundation that can break silently on any
upgrade.

---

## 2. Prior Art — The Drop-In Directory Pattern

This problem was solved in Unix system administration in the 1990s and is now
the standard pattern for extensible software configuration:

| System | Primary config | Drop-in directory | Owner |
|---|---|---|---|
| sudo | `/etc/sudoers` | `/etc/sudoers.d/` | root, packages |
| cron | `/etc/crontab` | `/etc/cron.d/` | root, packages |
| systemd | unit files | `/etc/systemd/system/*.d/` | admin, packages |
| PAM | `/etc/pam.conf` | `/etc/pam.d/` | root, packages |
| sysctl | `/etc/sysctl.conf` | `/etc/sysctl.d/` | root, packages |
| rsyslog | `/etc/rsyslog.conf` | `/etc/rsyslog.d/` | root, packages |
| git | `~/.gitconfig` | `~/.config/git/config.d/` | user |

The invariants of this pattern, consistent across all implementations:

1. **The software actively searches the drop-in directory** — no manual
   registration in the primary config required
2. **The drop-in directory is guaranteed not touched by the software** — it is
   owned by the caller (admin, user, package manager), never overwritten
3. **Load order is deterministic** — lexicographic on filename, numeric prefix
   is the convention for controlling order
4. **Each drop-in is self-contained** — name, purpose, and configuration in
   one unit
5. **Permission enforcement is strict** — wrong owner or world-writable =
   silently skipped with log entry
6. **Primary config continues to work unchanged** — drop-ins are additive

This PR applies that pattern to Claude Code's hook system.

---

## 3. Goals and Non-Goals

### Goals

- Provide a documented, reserved, upgrade-safe directory for user-supplied
  hook descriptors: `~/.claude/hooks.d/`
- Claude Code actively searches this directory at startup — no `settings.json`
  registration required
- Strict permission enforcement with logged violations
- Full load-order transparency in startup logs
- Identity logging: every hook execution records what ran, from where, and why
- Support for system-level hooks (`/etc/claude/hooks.d/`) for enterprise
  deployments
- Backward compatibility: existing `settings.json` hooks continue to work
  without modification

### Non-Goals

- Replacing `settings.json` hooks — they continue to work as-is
- A plugin marketplace or remote hook distribution
- Hook signing or cryptographic verification (out of scope for this PR;
  permission enforcement is the security model)
- Hot-reload of hooks during a session

---

## 4. Directory Structure

### Search path (in priority order, lowest to highest)

```
/etc/claude/hooks.d/          [1] System-managed — enterprise policy, root-owned
~/.claude/hooks.d/            [2] User-global — personal, roaming, dotfiles-managed
.claude/hooks.d/              [3] Project — checked into git, team-shared
.claude/hooks.d/local/        [4] Project-local — gitignored, machine-specific
```

Higher-priority entries do not replace lower-priority entries — all hooks from
all levels are collected and executed. Priority governs load order only: if
two hooks share the same numeric prefix, higher-priority path wins the slot.

### The `~/.claude/hooks.d/` guarantee

Claude Code explicitly reserves `~/.claude/hooks.d/` as user namespace:

- Claude Code never creates files in `~/.claude/hooks.d/`
- Claude Code never modifies or deletes files in `~/.claude/hooks.d/`
- Claude Code never traverses `~/.claude/hooks.d/` for any purpose other than
  hook discovery
- This guarantee is encoded in code comments, tests, and documentation and
  must be preserved by all future contributors

### Naming convention

```
~/.claude/hooks.d/
    00-enterprise-policy.json   # numeric prefix = load order (00–99)
    10-startup-audit.json
    20-autoground.json
    50-security-cleanup.json
    90-local-overrides.json
```

Files not matching `*.json` in `hooks.d/` are ignored (future extension space).
Subdirectories are ignored at this level (except `local/` in project context).

---

## 5. Hook Descriptor Format

Each `.json` file in `hooks.d/` is a hook descriptor. It declares one or more
hooks, their events, commands, and metadata.

### Schema

```json
{
    "name": "autoground",
    "version": "1.0.0",
    "description": "Query substrate DB and write prior_art_notes.md at session end",
    "author": "Mark Menkhus",
    "source": "https://github.com/menkhus/claude_code_management_scripts",
    "hooks": [
        {
            "event": "Stop",
            "command": "/Users/mark/.claude/user_scripts/autoground.py",
            "matcher": "",
            "timeout": 90,
            "enabled": true
        }
    ]
}
```

### Field definitions

| Field | Required | Description |
|---|---|---|
| `name` | yes | Human-readable identifier, unique within hooks.d |
| `version` | no | Semver string, for logging and diagnostics |
| `description` | no | One-line description, shown in startup log |
| `author` | no | For logging and attribution |
| `source` | no | URL to source repo or documentation |
| `hooks[].event` | yes | One of the supported hook events (see §7) |
| `hooks[].command` | yes | Absolute path to executable |
| `hooks[].matcher` | no | Tool name pattern for Pre/PostToolUse hooks |
| `hooks[].timeout` | no | Seconds before hook is killed (default: 60) |
| `hooks[].enabled` | no | If false, hook is loaded but not executed (default: true) |

### Requirements on `hooks[].command`

- Must be an absolute path (no `~` expansion — Claude Code does not expand
  tilde in hook commands on all platforms; this must be enforced at descriptor
  validation time with a clear error message)
- Must exist at the path specified
- Must be executable by the running user
- Must pass permission checks (see §6)

---

## 6. Security and Permission Model

Every hook descriptor file and every command it references is subject to
permission enforcement before execution. This mirrors the model used by sudo,
cron, and SSH authorized_keys.

### Descriptor file checks

| Check | Violation action |
|---|---|
| File owner == running user (or root for /etc/ path) | Skip descriptor, log WARNING |
| File mode: not group-writable (not g+w) | Skip descriptor, log WARNING |
| File mode: not world-writable (not o+w) | Skip descriptor, log WARNING |
| Valid JSON | Skip descriptor, log ERROR |
| Schema validates | Skip descriptor, log ERROR |

### Command file checks (for each hook in descriptor)

| Check | Violation action |
|---|---|
| Path is absolute | Skip hook, log ERROR |
| File exists | Skip hook, log WARNING |
| File owner == running user (or root for /etc/ path) | Skip hook, log WARNING |
| File mode: not group-writable | Skip hook, log WARNING |
| File mode: not world-writable | Skip hook, log WARNING |
| File is executable | Skip hook, log WARNING |

### Rationale

Cron, sudo, and SSH apply exactly these checks for the same reason: a
world-writable hook script is an escalation vector. Any process on the machine
can modify the script to run arbitrary commands with the user's privileges at
the next session boundary. Refusing to execute and logging the violation is
the correct response — not a silent skip.

### Logging format for violations

```
[hooks.d] WARN  skipped: ~/.claude/hooks.d/20-autoground.json
          reason: command /Users/mark/.claude/user_scripts/autoground.py is world-writable
          fix: chmod o-w /Users/mark/.claude/user_scripts/autoground.py
```

The `fix:` line is required — users should not have to guess what to do.

---

## 7. Load Algorithm

Claude Code executes the following at hook registration time (session start):

```
1. Collect descriptor files from all search paths, in priority order:
       /etc/claude/hooks.d/*.json          (if path exists)
       ~/.claude/hooks.d/*.json
       <cwd>/.claude/hooks.d/*.json        (if path exists)
       <cwd>/.claude/hooks.d/local/*.json  (if path exists)

2. Within each path, sort files lexicographically by filename.

3. For each descriptor file:
   a. Check descriptor file permissions (§6). Skip + log on violation.
   b. Parse JSON. Skip + log on parse error.
   c. Validate schema. Skip + log on schema error.
   d. For each hook in descriptor:
      i.  Check command permissions (§6). Skip + log on violation.
      ii. Register hook: add to event dispatch table for hooks[].event
          with metadata (name, version, source path, timeout).

4. Log discovery summary to ~/.claude/logs/hooks.log:
       [hooks.d] loaded 3 hooks from 3 descriptors
       [hooks.d]   Stop        20-autoground.json        autoground v1.0.0
       [hooks.d]   Stop        50-security-cleanup.json  claude-settings-cleanup v2.1.0
       [hooks.d]   SessionStart 10-startup-audit.json    startup-audit v1.0.0
```

### Merge with settings.json hooks

Hooks from `settings.json` (existing mechanism) and hooks from `hooks.d/`
are merged into the same dispatch table. Execution order within an event:

1. `settings.json` hooks (existing behavior, unchanged)
2. `hooks.d/` hooks in load order

This ensures backward compatibility: no existing behavior changes.

---

## 8. Execution and Identity Logging

Every hook execution is logged. This is not optional — it is required for
security auditability and debugging.

### Log entry format

```
[hooks.d] EXEC  event=Stop  hook=autoground  source=~/.claude/hooks.d/20-autoground.json
          command=/Users/mark/.claude/user_scripts/autoground.py
          started=2026-04-09T22:15:33Z
          exit=0  duration=1.4s
```

On failure:
```
[hooks.d] EXEC  event=Stop  hook=autoground  source=~/.claude/hooks.d/20-autoground.json
          command=/Users/mark/.claude/user_scripts/autoground.py
          started=2026-04-09T22:15:33Z
          exit=1  duration=0.8s
          stderr: [autoground hook] failed — see ~/.claude/logs/autoground.log
```

On timeout:
```
[hooks.d] EXEC  event=Stop  hook=autoground
          command=/Users/mark/.claude/user_scripts/autoground.py
          started=2026-04-09T22:15:33Z
          killed=timeout(90s)
```

### Log file

`~/.claude/logs/hooks.log`

- Appended, not overwritten, across sessions
- Rotated at 10MB (rename to `hooks.log.1`, new `hooks.log` created)
- Keep 3 rotations maximum
- Log lines are ISO8601 timestamped

---

## 9. Supported Hook Events

All existing Claude Code hook events are supported. For reference:

| Event | When it fires |
|---|---|
| `SessionStart` | At session initialization, before first prompt |
| `Stop` | At session end (every response completion) |
| `PreToolUse` | Before any tool call; can block execution |
| `PostToolUse` | After any tool call completes |
| `PostToolUseFailure` | After a tool call fails |
| `UserPromptSubmit` | Before user prompt is sent to model |
| `WorktreeCreate` | When a git worktree is created |
| `WorktreeRemove` | When a git worktree is removed |

---

## 10. Backward Compatibility

This PR is strictly additive. Existing behavior is unchanged:

- `settings.json` hooks continue to work exactly as before
- No settings.json keys are deprecated
- No breaking changes to hook execution behavior
- Users who do nothing notice no difference

The only new behavior is: Claude Code now also searches `hooks.d/` directories
and loads descriptors found there.

---

## 11. Migration Path

For users currently registering hooks via `settings.json`:

**Before:**
```json
{
  "hooks": {
    "Stop": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "/Users/mark/.claude/scripts/autoground.py"
      }]
    }]
  }
}
```

**After (optional migration):**
```sh
mkdir -p ~/.claude/hooks.d
cat > ~/.claude/hooks.d/20-autoground.json << 'EOF'
{
    "name": "autoground",
    "version": "1.0.0",
    "description": "Substrate DB grounding hook",
    "hooks": [{
        "event": "Stop",
        "command": "/Users/mark/.claude/user_scripts/autoground.py",
        "timeout": 90
    }]
}
EOF
# Remove the equivalent entry from settings.json
```

Migration is optional — both mechanisms work simultaneously.

---

## 12. Code Changes Required

### Files modified in anthropics/claude-code

1. **Hook loading module** (wherever `settings.json` hooks are parsed and
   registered): add `loadHooksFromDropInDirectories()` called after
   `loadHooksFromSettings()`. Merge results into the same dispatch table.

2. **Permission checker**: new function `validateHookDescriptor(path)` and
   `validateHookCommand(path)` implementing the checks in §6.

3. **Logger**: extend hook execution logging to include `source` (which
   descriptor file registered this hook) for all hook events.

4. **Settings schema**: add `hooks.d/` directory paths to the documented
   search path list.

5. **Startup sequence**: after hook loading, emit discovery summary to
   `~/.claude/logs/hooks.log` and optionally to debug output.

### New files

6. **`docs/user-hooks.md`**: user-facing documentation of the `hooks.d/`
   convention, descriptor format, permission requirements, and examples.

7. **`docs/enterprise-hooks.md`**: admin-facing documentation for
   `/etc/claude/hooks.d/` deployment.

### Tests required

8. **Unit: permission enforcement** — world-writable descriptor skipped,
   world-writable command skipped, missing command skipped.

9. **Unit: descriptor parsing** — valid descriptor loads, malformed JSON
   skipped, missing required fields skipped.

10. **Unit: load order** — numeric prefix determines order, system before user
    before project before local.

11. **Integration: merge with settings.json** — both fire for the same event
    in the correct order.

12. **Regression: settings.json hooks unchanged** — all existing hook behavior
    works identically when `hooks.d/` is empty.

13. **Invariant test: hooks.d/ not written** — Claude Code operations (start,
    stop, upgrade simulation) do not create or modify files in `hooks.d/`.

---

## 13. Documentation Changes Required

### README.md

Add a section: **User Hook Scripts**. Point to `docs/user-hooks.md`.
One paragraph in the README is enough — depth goes in docs.

### docs/user-hooks.md (new)

Full user guide:
- What `hooks.d/` is and why it exists
- The upgrade-safe guarantee (explicit, prominent)
- Descriptor format with annotated example
- Permission requirements and how to verify them
- How to check what hooks are loaded (`cat ~/.claude/logs/hooks.log`)
- Migration from `settings.json`
- Troubleshooting: hook not firing, permission violation, path errors

### CHANGELOG

Entry describing the new feature with the PR number.

---

## 14. Reference Implementation

The following hook descriptors and scripts demonstrate the pattern and ship
with this PR as working examples in `docs/examples/`:

- `docs/examples/hooks.d/50-security-cleanup.json` + `claude-settings-cleanup.sh`
  — clears `permissions.allow` on session exit
- `docs/examples/hooks.d/10-startup-audit.json` + `claude-startup-audit.py`
  — audits CLAUDE.md chain size and MCP server count at session start

These are not installed automatically — they are reference implementations that
users can copy into `~/.claude/hooks.d/` and adapt.

---

## 15. Open Questions for Anthropic Review

1. **`/etc/claude/hooks.d/` scope**: enterprise path is in-design but could be
   deferred to a follow-up PR. Recommend including it — the search path
   abstraction is easier to add now than retrofit later.

2. **Descriptor format**: JSON is proposed. TOML or YAML would also work.
   JSON is consistent with existing `settings.json` and `mcp.json` usage in
   Claude Code — recommend JSON.

3. **`hooks.d/` vs. `hooks/`**: the `.d` suffix is the Unix convention (cron.d,
   sudoers.d) and signals "drop-in directory" to experienced admins. Recommend
   `hooks.d/`.

4. **Absolute path enforcement**: the current hook system already requires
   absolute paths in `settings.json` (tilde not expanded on all platforms).
   Descriptor validation should enforce this explicitly with a clear error
   message rather than silently failing.

5. **`enabled: false` behavior**: proposed above as a way to disable a hook
   without removing the descriptor. Alternative: move the file out. Either
   works; `enabled` field is more operator-friendly for enterprise deployments
   where the descriptor is managed by configuration management.

---

## 16. Why This Matters

Claude Code's hook system is one of its strongest features. It enables
automation, security enforcement, and session continuity that no other AI
coding assistant supports. But hooks are only as durable as the infrastructure
supporting them.

Users who have invested in hooks — security cleanup, startup auditing,
autogrounding, prompt preprocessing — deserve a foundation that survives
upgrades, works across machines, and behaves consistently. The drop-in
directory pattern is forty years old, proven at scale, and universally
understood by the engineers most likely to write hooks.

This PR gives those users a foundation they can rely on.

---

*Submitted by Mark Menkhus (github.com/menkhus) and Claude Sonnet 4.6 (Anthropic).
Design and reference implementation developed collaboratively, April 2026.*

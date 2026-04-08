# Claude Code Context Loading Rules — The Rules of the Road

Documented 2026-04-07. Sources: official Claude Code documentation.
Confidence levels noted where behavior is inferred vs. explicitly documented.

---

## The Mental Model: Unix Profiles, But Accumulating

Think of CLAUDE.md like the old Unix profile chain — `/etc/profile` → `~/.profile`
— except the key difference is **nothing overrides anything**. It all
accumulates. Every ancestor CLAUDE.md is concatenated into context. There is no
`export` that wins. Claude reads all of it and interprets conflicts as best it can.

This is the root cause of "too much seasoning."

---

## 1. CLAUDE.md Load Order

**Direction: bottom-up** (cwd → ancestors, up to filesystem root)

When Claude Code starts in `/Users/mark/Documents/src/My_AI_work/aifilter-project/`:

| Load order | File | Loaded at startup? |
|---|---|---|
| 1st | `/Library/Application Support/ClaudeCode/CLAUDE.md` | Yes — mandatory, cannot exclude |
| 2nd | `/Users/mark/CLAUDE.md` | Yes |
| 2nd | `/Users/mark/CLAUDE.local.md` | Yes (if exists) |
| 3rd | `/Users/mark/Documents/CLAUDE.md` | Yes |
| 3rd | `/Users/mark/Documents/CLAUDE.local.md` | Yes (if exists) |
| 4th | `/Users/mark/Documents/src/CLAUDE.md` | Yes (if exists) |
| 5th | `/Users/mark/Documents/src/My_AI_work/CLAUDE.md` | Yes |
| 6th | `/Users/mark/Documents/src/My_AI_work/aifilter-project/CLAUDE.md` | Yes |
| — | `~/.claude/CLAUDE.md` | Yes — user-level, all projects |
| — | `~/.claude/rules/*.md` | Yes (without paths frontmatter) |
| — | `.claude/rules/*.md` | Yes (without paths frontmatter) |

**Subdirectory CLAUDE.md files** (below cwd): NOT loaded at startup.
Loaded lazily when Claude reads files in that subdirectory.

**CLAUDE.local.md**: Same as CLAUDE.md but gitignored by convention — for
personal instructions you don't want committed to the repo.

### Exclusion Escape Hatch

You can exclude specific ancestor files without deleting them:

```json
// .claude/settings.local.json
{
  "claudeMdExcludes": [
    "/Users/mark/Documents/CLAUDE.md",
    "**/My_AI_work/CLAUDE.md"
  ]
}
```

### Import System

CLAUDE.md files can pull in other files:

```
@docs/conventions.md
@.claude/rules/python-style.md
```

Expanded inline at load time. Max 5 levels deep.

---

## 2. Override vs. Merge — The Critical Table

| Thing | Behavior | What this means |
|---|---|---|
| CLAUDE.md files | **Accumulate** (concatenate) | All ancestors load; conflicts unresolved |
| settings scalars | **Override** (higher precedence wins) | Project beats user beats global |
| settings arrays (permissions.allow, etc.) | **Merge** (deduplicate across all scopes) | Allow lists grow from all sources |
| settings objects (env, hooks) | **Deep merge** by key | Both apply unless same key |
| permissions.deny | **Absolute** (deny beats any allow) | Denylist always wins |
| MCP servers (same name) | **Override** (local > project > user) | More specific wins |
| MCP servers (different names) | **Merge** | All available |
| Auto memory | **Accumulate** | Claude keeps adding; never auto-trims |

**The "too much seasoning" problem in one line:**
CLAUDE.md files accumulate, permissions.allow arrays merge, and auto memory
accumulates — there is no mechanism that trims any of it automatically.

---

## 3. Settings Precedence (Highest to Lowest)

```
Managed settings  (/Library/Application Support/ClaudeCode/)  ← cannot override
  └─ Command-line flags                                         ← session only
       └─ .claude/settings.local.json                          ← local project
            └─ .claude/settings.json                           ← shared project
                 └─ ~/.claude/settings.json                    ← user global
```

Project-level beats user-level for scalars.
But arrays from ALL levels merge together — so permissions.allow is the union
of what every level contributes.

---

## 4. What Lives Where

```
/Library/Application Support/ClaudeCode/
  CLAUDE.md                    Org-level mandatory instructions
  managed-settings.json        Org policy (MDM-deployed)

~/.claude/
  settings.json                User global settings + hooks
  settings.local.json          User global personal overrides
  CLAUDE.md                    User instructions (all projects)
  rules/                       Personal rules (all projects)
  agents/                      Personal subagents
  user_hook_scripts/           Hook scripts (Mark's convention, not native)
  projects/<id>/memory/
    MEMORY.md                  Auto memory index (first 200 lines loaded)
    *.md                       Topic files (loaded on demand)

<project-root>/
  CLAUDE.md                    Project instructions (committed)
  CLAUDE.local.md              Personal project instructions (gitignored)
  .mcp.json                    Project MCP servers (committed)
  .claude/
    settings.json              Project settings (committed)
    settings.local.json        Personal project settings (gitignored)
    rules/                     Project rules
      *.md (no frontmatter)    Loaded at startup
      *.md (with paths:)       Loaded on demand for matching files
    agents/                    Project subagents
```

---

## 5. MCP Server Load Order

```
~/.claude.json (user-scoped servers)        ← lowest priority
  └─ .mcp.json (project-scoped)             ← overrides user if same name
       └─ local scope                       ← highest priority
            └─ managed-mcp.json             ← org policy (cannot override)
```

Same server name = more specific wins (override).
Different server names = all merge (accumulate).

**The global tax:** Servers in `~/.mcp.json` inject their full tool schemas
into every session for every project. 5 servers ≈ 15–20k tokens regardless
of whether the project uses them.

---

## 6. Multiple Claude Code Instances

CLI, VS Code extension, and Desktop app all share:
- `~/.claude/settings.json`
- `CLAUDE.md` files
- `~/.claude/projects/<id>/memory/`
- `.mcp.json` server definitions
- Session history (resumable with `claude --resume`)

What is NOT shared between machines:
- Everything above — it's all machine-local
- Auto memory does not sync to cloud (exception: Claude Code on claude.ai/code)

---

## 7. The Auto Memory System

`~/.claude/projects/<project-id>/memory/` — written by Claude, not you.

- **MEMORY.md**: The index. First 200 lines (or 25KB) loaded every session.
- **Topic files** (e.g., `debugging.md`): Loaded on demand when relevant.
- Project identity = git repo root (same across all subdirs and worktrees).
- Machine-local only. No cloud sync.

**MEMORY.md is a native Claude Code concept** — not a user convention.
Claude Code creates and manages it. The system described in `~/.claude/user_hook_scripts/`
uses the same location but the index format is a convention, not enforced by the tool.

**Auto memory accumulates.** Claude adds to it; nothing trims it automatically.
The 200-line cap on MEMORY.md loading provides a soft ceiling.

---

## 8. The Accumulation Problem — Summary

Every mechanism that feels like "configuration" actually accumulates:

| Mechanism | Accumulates because... |
|---|---|
| CLAUDE.md | Concatenated, not merged with override |
| permissions.allow | Array-merged across all settings scopes |
| Auto memory | Claude writes; never auto-trims |
| `.claude/rules/` | All non-scoped rules load at startup |
| MCP servers | Different-named servers all merge |

**The only mechanisms with override semantics:**
- Settings scalar values (project beats user)
- MCP server definitions with same name (local beats project beats user)
- permissions.deny (always beats allow)

---

## 9. Practical Guidance — Rules of the Road

**For ~/CLAUDE.md:**
Shell environment, key tools, nothing project-specific. Target: under 2KB.
Loads for every session on this machine. Every byte costs every time.

**For ~/Documents/CLAUDE.md and intermediate dirs:**
Orientation only if you regularly start Claude from that directory.
Otherwise: delete it or leave it empty. Under 1KB.

**For project CLAUDE.md:**
Current status, open issues, quick commands, next steps. Not a diary.
Archive completed sprints to git log or docs/. Target: under 4KB.

**For .claude/rules/:**
Use `paths:` frontmatter to scope rules to specific file types.
Rules without `paths:` load for every session — treat them like CLAUDE.md.

**For MCP servers:**
Only put in `~/.mcp.json` what every project needs.
Move project-specific servers to `.mcp.json` in the project root.

**For auto memory:**
The 200-line cap is your friend. Keep MEMORY.md index entries short.
Prune stale topic files periodically — they don't auto-expire.

**For permissions.allow:**
Cleared automatically by the exit hook. Nothing to manage manually.

# Claude Code Context Loading Rules — Verified Against Source Code

Documented 2026-04-07.
**Source:** Official docs + binary analysis of Claude Code v2.1.94
(`~/.local/share/claude/versions/2.1.94` — Bun single executable, JS bundle embedded)

Where docs and code disagree, the code wins. Discrepancies are called out explicitly.

---

## The Mental Model: Unix Profiles, But Everything Accumulates

Think of CLAUDE.md like the old Unix profile chain — `/etc/profile` → `~/.profile`
— except **nothing overrides anything**. It all accumulates. Every ancestor
CLAUDE.md is concatenated into context. There is no `export` that wins.
Claude reads all of it and interprets conflicts as best it can.

This is the root cause of "too much seasoning."

---

## 1. CLAUDE.md — Actual Load Order (from source)

The loader walks **up** from cwd to filesystem root, then **reverses** the list
so ancestors load first (root → cwd). At each directory level it tries:

```
<dir>/CLAUDE.md               type "Project"
<dir>/.claude/CLAUDE.md       type "Project"
<dir>/.claude/rules/*.md      type "Project"  (all .md files, no-paths frontmatter only)
<dir>/CLAUDE.local.md         type "Local"    (if localSettings enabled)
```

For a session starting in `~/Documents/src/My_AI_work/aifilter-project/`:

| Order | File |
|---|---|
| 1 | `~/.claude/managed/CLAUDE.md` (enterprise policy — cannot exclude) |
| 2 | `~/.claude/managed/rules/*.md` (enterprise policy) |
| 3 | `~/.claude/CLAUDE.md` (user-level, all projects) |
| 4 | `~/.claude/rules/*.md` (user-level) |
| 5 | `/CLAUDE.md` (filesystem root, if exists) |
| … | … every ancestor directory … |
| N-3 | `~/Documents/src/CLAUDE.md` |
| N-2 | `~/Documents/src/My_AI_work/CLAUDE.md` |
| N-1 | `~/Documents/src/My_AI_work/aifilter-project/CLAUDE.md` |
| N-1 | `~/Documents/src/My_AI_work/aifilter-project/.claude/CLAUDE.md` |
| N | AutoMem (feature-flag gated — loaded last) |

**Subdirectory CLAUDE.md files** (below cwd): NOT loaded at startup.
Loaded lazily when Claude reads files in that subdirectory.

### Excluding Specific Files

`claudeMdExcludes` in settings is **confirmed implemented** in source — uses
picomatch with `dot:true`. Cannot exclude Managed type.

```json
// .claude/settings.local.json
{
  "claudeMdExcludes": [
    "/Users/mark/Documents/CLAUDE.md",
    "**/My_AI_work/CLAUDE.md"
  ]
}
```

### The Hidden Extra: .mcp.json Also Walks Ancestors

**Docs say:** `.mcp.json` is read from the project root.
**Code says:** It walks every ancestor directory from filesystem root to cwd,
merging all `.mcp.json` files it finds. Closer-to-cwd entries win for scalars.
This means a `~/.mcp.json` AND a `~/Documents/src/.mcp.json` AND a
`./project/.mcp.json` could all be active simultaneously.

---

## 2. Override vs. Merge — What the Code Actually Does

| Thing | Behavior | Source evidence |
|---|---|---|
| CLAUDE.md files | **Accumulate** (concatenated, deduplicated by path) | `A.push(J)` after `!q.has(X)` check |
| Settings scalars | **Last-loaded wins** (local > project > user) | lodash `mergeWith`, undefined → last wins |
| Settings arrays (`permissions.allow`, `deny`, etc.) | **MERGE + deduplicate across ALL sources** | `UV9`: `s9([...H,..._])` |
| MCP servers (same name) | **Later/closer-to-cwd wins** | spread: `{...A,...q}` |
| MCP servers (different names) | **All merge** | accumulate into server map |
| `permissions.deny` | **Accumulates like allow** — but deny beats allow at eval | same merge, checked first at runtime |
| AutoMem | **Accumulates** — Claude writes, nothing trims | appended last, no trim mechanism |

### The Critical Misunderstanding About Permissions

**What most people believe:** "My project's settings.local.json overrides
what the user settings allow."

**What the code does:** ALL `permissions.allow` arrays from ALL settings
files are concatenated and deduplicated into one big list.

**Consequence:** You cannot revoke a permission granted in a parent settings
file by writing a different value in a child file. The only way to remove
a permission is to delete it from the file that granted it.

**`permissions.deny` works the same way** — it accumulates too. But deny
always beats allow at evaluation time, so a deny in any file blocks a
tool regardless of what other files allow.

---

## 3. Settings Precedence (Verified)

For **scalar values** (strings, booleans), last-loaded wins:

```
Managed settings  (~/.claude/managed-settings.json)   ← loaded into base
  └─ User         (~/.claude/settings.json)
       └─ Project (.claude/settings.json)
            └─ Local (.claude/settings.local.json)    ← last = wins for scalars
```

For **arrays** (`permissions.allow`, `deny`, `ask`): ALL sources contribute.
The final list is the union of all, deduplicated.

---

## 4. What Lives Where (Verified)

```
~/.claude/managed/
  CLAUDE.md                    Enterprise policy — always loads, cannot exclude
  rules/*.md                   Enterprise rules

~/.claude/
  settings.json                User global settings + hooks
  settings.local.json          User global personal overrides
  CLAUDE.md                    User instructions (loads for all projects)
  rules/                       Personal rules (load for all projects)
  agents/                      Personal subagents (all projects)
  user_hook_scripts/           Hook scripts (Mark's convention — not native)
  projects/<id>/memory/
    MEMORY.md                  Auto memory index (first 200 lines loaded)
    *.md                       Topic files (loaded on demand)

<project-root>/
  CLAUDE.md                    Project instructions (committed)
  CLAUDE.local.md              Personal project instructions (gitignored by convention)
  .mcp.json                    Project MCP servers (also checked in ancestor dirs)
  .claude/
    settings.json              Shared project settings (committed)
    settings.local.json        Personal project settings (NOT auto-gitignored — see below)
    rules/
      *.md (no paths:)         Loaded at startup for every session
      *.md (with paths:)       Loaded on demand for matching file patterns
    agents/                    Project subagents
```

### settings.local.json Is NOT Auto-Gitignored

**Docs imply** it should be gitignored.
**Code confirms** the write path does NOT add it to .gitignore automatically.
You must do this yourself — hence `~/.gitignore_global`.

---

## 5. MCP Server Loading (Verified)

Servers come from multiple sources, all merged:

| Source | Scope | Precedence |
|---|---|---|
| `~/.claude/managed-mcp.json` | Enterprise | Highest — cannot override |
| `~/.claude/settings.local.json` mcpServers | Local | High |
| `~/.claude/settings.json` mcpServers | User | Medium |
| `.mcp.json` (cwd + all ancestors) | Project | Lower |
| Plugin manifests | Plugin | Lowest |

New `.mcp.json` servers prompt for approval. Approvals stored in
`localSettings.enabledMcpjsonServers`. `enableAllProjectMcpServers: true`
bypasses per-server prompts — which is the state of most of Mark's projects,
meaning all 5 global MCP servers load for every project.

---

## 6. AutoMem (Memory System)

**Feature-flag gated** — not unconditionally active. Gated on a Statsig flag
in the binary. Behavior may differ across accounts/versions.

When active:
- Loaded **last**, after all CLAUDE.md files
- Deduplicated against already-loaded paths
- Path is dynamic (from `lZ_()` — project-specific)
- `~/.claude/projects/<id>/memory/MEMORY.md` — first 200 lines loaded per session
- Topic files loaded on demand

The `/memory` command writes to `~/.claude/CLAUDE.md` (User scope) or
`<cwd>/CLAUDE.md` (Project scope) depending on git status. It does NOT write
to a separate memory directory — that is the auto-memory convention used by
the Claude Code system prompt, not a separate file system.

---

## 7. Multiple Instances

CLI, VS Code extension, Desktop app all share:
- All settings files
- All CLAUDE.md files
- All MCP server configs
- Memory (`~/.claude/projects/<id>/memory/`)
- Session history (`claude --resume`)

Machine-local only — nothing syncs across machines except Claude Code on claude.ai/code (web).

---

## 8. What Could Go Wrong — A Realistic List

Given the accumulation-everywhere model:

1. **Conflicting instructions in CLAUDE.md ancestors** — Claude reads all of
   them and tries to reconcile. If `~/CLAUDE.md` says "use yarn" and the project
   says "use npm", Claude picks one. You don't know which.

2. **permissions.allow you can't revoke** — A permission granted anywhere
   in the settings chain stays granted. Removing it requires finding which
   file added it. The exit hook solves this for project allow lists, but not
   for `~/.claude/settings.json` entries.

3. **MCP servers in unexpected ancestor dirs** — A `.mcp.json` in `~/Documents/src/`
   loads for every project under that tree. Easy to forget it's there.

4. **.claude/rules/ files loading unexpectedly** — Any `.md` without `paths:`
   frontmatter in any `.claude/rules/` directory in any ancestor loads at startup.

5. **AutoMem writing to the wrong CLAUDE.md** — The `/memory` command writes to
   `~/.claude/CLAUDE.md` (User) or `./CLAUDE.md` (Project) — not a separate file.
   It can add content to files you're managing manually.

6. **enableAllProjectMcpServers: true** in settings.local.json bypasses
   per-server approval for all `.mcp.json` servers — including ones you didn't
   intend to enable. Most of Mark's projects have this set.

7. **claudeMdExcludes in the wrong settings file** — It reads from the
   effective merged settings. It works in any settings file, but if you put
   it in a project file intending to exclude a parent, verify the path matches
   exactly (picomatch, absolute paths, `dot:true`).

# claude_code_management_scripts

Systems management tooling for Claude Code — hooks, scripts, and documentation
for keeping a large multi-project Claude Code installation healthy.

**Created:** 2026-04-07
**Author:** Mark Menkhus
**Context:** ~20 months of Claude Code use across 60+ projects revealed a set of
systemic hygiene problems. This project documents them, provides remediation
tools, and establishes ongoing monitoring via hooks.

---

## The Problem

Claude Code is excellent at individual tasks. It is not excellent at managing
its own footprint across a long-lived, multi-project installation. After 20
months of daily use across `~/Documents/src/`, `~/src/`, and `~/writing/`, the
following deficits accumulated silently:

1. **Token bloat at startup** — CLAUDE.md files are cumulative up the directory
   tree. Every ancestor directory's CLAUDE.md loads. A session starting in a
   deeply nested project can burn 50k tokens before you type anything.

2. **Credential leakage** — `settings.local.json` persists every approved
   tool-call permission verbatim, including `export API_KEY="sk-ant-..."` from
   one-shot bash approvals. No expiry. No secrets detection. Silently accumulates.

3. **Stale permissions** — Wildcard and one-shot permissions in
   `settings.local.json` persist forever across sessions. The allow list grows
   monotonically.

4. **Global MCP servers taxing every project** — MCP servers configured in
   `~/.mcp.json` inject their full tool schemas into every session regardless of
   whether the project uses them. 5 global servers ≈ 15–20k tokens per session.

5. **CLAUDE.md files grow without discipline** — Session summaries, completed
   sprint history, stale file trees, and architecture notes accumulate. No
   mechanism trims them. A project CLAUDE.md that started at 2KB can reach 20KB.

6. **`.claude/` directory files auto-load** — Any `.md` file placed in a
   project's `.claude/` directory is loaded into context automatically. Easy to
   create accidentally bloated context (e.g. a CONTEXT-MANAGEMENT-GUIDE.md that
   consumes the context it was meant to manage).

7. **No startup awareness** — There is no built-in warning when you are starting
   a session with an unusually large context load. You find out when the model
   starts forgetting things mid-session.

---

## What This Project Provides

### Hooks (`hooks/`)
Shell scripts wired into Claude Code's lifecycle via `~/.claude/settings.json`.

| Hook | Event | Purpose |
|---|---|---|
| `claude-settings-cleanup.sh` | Stop | Clears `permissions.allow` on exit |
| `claude-startup-audit.sh` | (planned) | Warns on high startup token load |

Hooks are installed to `~/.claude/user_hook_scripts/` and registered in
`~/.claude/settings.json`.

### Scripts (`scripts/`)
Standalone tools for one-time or recurring maintenance.

| Script | Purpose |
|---|---|
| (planned) `bulk-clean-settings.sh` | Bulk-clear allow lists across all projects |
| (planned) `audit-claude-md-sizes.sh` | Report CLAUDE.md token estimates by project |
| (planned) `audit-mcp-scope.sh` | Show which MCP servers are global vs. project-scoped |

### Docs (`docs/`)
Reference documentation for understanding and managing Claude Code's systems.

| Doc | Contents |
|---|---|
| `context-token-budget.md` | What loads at startup and how many tokens each costs |
| `settings-local-json-risk.md` | The credential leakage problem and remediation |
| `claude-md-discipline.md` | Guidelines for keeping CLAUDE.md files lean |
| `mcp-server-scoping.md` | How to move global MCP servers to per-project scope |

### Todo (`todo/`)
Tracked work items. See `todo/TODO.md`.

---

## Quick Reference: What Loads at Startup

When Claude Code starts in a project directory, it loads (in order):

1. Claude Code system prompt (~10–15k tokens, fixed)
2. All `CLAUDE.md` files from `~` down to the project root (cumulative)
3. All `.md` files in the project's `.claude/` directory
4. All enabled skill/plugin SKILL.md files
5. MCP server tool schemas for all configured servers (`~/.mcp.json` + project `.mcp.json`)
6. Memory index (`MEMORY.md` from the project's memory directory)

Items 2–6 are controllable. Item 1 is not.

---

## Installation

The exit hook is already active on this machine. See `hooks/` for scripts and
`~/.claude/user_hook_scripts/` for the installed copies.

For a new machine, see `docs/new-machine-setup.md` (planned).

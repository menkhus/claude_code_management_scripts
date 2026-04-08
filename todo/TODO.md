# TODO — claude_code_management_scripts

Findings from the 2026-04-07 audit of a 20-month Claude Code installation.
Ordered by impact (highest first).

---

## DONE ✅

- [x] **Exit hook: clear permissions.allow on session end**
      Script: `~/.claude/user_hook_scripts/claude-settings-cleanup.sh`
      Hook: Stop event in `~/.claude/settings.json`
      Impact: Prevents credential accumulation and stale permission growth.

- [x] **Bulk-clear existing stale permissions.allow**
      Ran cleanup across 69 `settings.local.json` files.
      Removed live API key (`sk-ant-*`) from aifilter-project.

- [x] **Global gitignore: protect settings.local.json**
      `~/.gitignore_global` now excludes `.claude/settings.local.json`.
      `git config --global core.excludesfile ~/.gitignore_global` set.

---

## HIGH IMPACT

- [ ] **Startup token audit hook (PreToolUse or startup script)**
      Write a hook that fires at session start, estimates the token load from
      CLAUDE.md files and `.claude/*.md` files in the current project tree,
      and prints a warning if it exceeds a threshold (e.g. 10k tokens from
      controllable sources).
      Script: `hooks/claude-startup-audit.sh`
      Hook event: investigate whether Claude Code supports a Start/PreSession hook.
      Fallback: a standalone script to run manually before starting a session.

- [ ] **Scope MCP servers per-project, not globally**
      Currently 5 servers in `~/.mcp.json` load for every project:
      `file-metadata`, `context-planner`, `docstory`, `ghost`, `semantic-ai-web`
      Estimated cost: 15–20k tokens per session regardless of project.
      Action: Audit which projects actually use each server. Move servers to
      per-project `.mcp.json`. Keep only truly universal servers global.
      Doc: `docs/mcp-server-scoping.md`

- [ ] **Trim aifilter-project CLAUDE.md (20KB → target 4KB)**
      Current state: 20KB, ~5k tokens. Contains completed sprint history,
      stale file trees, session summaries from 2024-11-04 that are now dead.
      Action: Extract the active state (current sprint, open bugs, next steps).
      Archive the history to `docs/` or git log.
      Guideline: A project CLAUDE.md should be orientation, not a diary.

- [ ] **Remove or drastically trim `.claude/CONTEXT-MANAGEMENT-GUIDE.md`**
      Located: `aifilter-project/.claude/CONTEXT-MANAGEMENT-GUIDE.md` (11.6KB)
      Irony: A context management guide consuming ~3k tokens every session.
      Action: Delete or move out of `.claude/` (files there auto-load).

---

## MEDIUM IMPACT

- [ ] **Audit all CLAUDE.md files for size discipline**
      Write `scripts/audit-claude-md-sizes.sh` to report size + estimated tokens
      for every CLAUDE.md in `~/Documents/src`, `~/src`, `~/writing`.
      Flag any over 8KB (>2k tokens) for review.

- [ ] **Document CLAUDE.md discipline guidelines**
      Write `docs/claude-md-discipline.md` with rules:
      - What belongs: current status, open issues, commands quick ref, next steps
      - What doesn't: session summaries, completed sprint details, stale file trees
      - Size target: under 4KB per project file, under 2KB for parent directories
      - Maintenance: prune before each new sprint, not after

- [ ] **Audit `~/CLAUDE.md` and `~/Documents/CLAUDE.md` for necessity**
      These load for every single session across all projects.
      `~/CLAUDE.md` (4.2KB) documents shell environment, key projects, and tools.
      `~/Documents/CLAUDE.md` (2.4KB) is orientation for top-level sessions.
      Question: Does a session in a specific project need to know about rss_miner?
      Consider: Move project inventory to a file that only loads when needed.

- [ ] **Establish `.claudeignore` hygiene**
      Some projects have `.claudeignore`. Standardize what to exclude.
      Large generated dirs, `node_modules`, `.venv`, build artifacts, etc.
      Document in `docs/claudeignore-patterns.md`.

---

## LOW IMPACT / FUTURE

- [ ] **Document the full token budget for a typical session**
      Write `docs/context-token-budget.md` with a worked example.
      Include: how to measure, what the model's effective working context is
      after fixed overhead, and what that means for long sessions.

- [ ] **New machine setup doc**
      Write `docs/new-machine-setup.md` covering:
      - Install claude-settings-cleanup hook
      - Configure ~/.gitignore_global
      - Scope MCP servers correctly
      - CLAUDE.md templates for home and project level

- [ ] **Consider credential scanning as part of the exit hook**
      After clearing permissions.allow, scan the file for any remaining
      secret-shaped strings (sk-ant-, Bearer, password=) and warn.
      This catches secrets that ended up in other fields (deny, MCP config, etc.)

---

## NOTES

**On the credential leak:** The exposed `sk-ant-api03-*` key in aifilter-project
should be rotated at console.anthropic.com. It appeared in session history and
was in plaintext in settings.local.json for months.

**On CLAUDE.md bloat:** Claude Code has no built-in mechanism to trim CLAUDE.md
files. The model will helpfully add to them but rarely suggests removing content.
This is a structural incentive problem — adding context feels safer than removing
it, but the cost compounds across every future session.

**On MCP server scope:** Claude Code's `enableAllProjectMcpServers: true` in
settings.local.json means every MCP server in `~/.mcp.json` loads for every
project. This is the current state across most projects here. The fix requires
intentional per-project `.mcp.json` files and removing the global catch-all.

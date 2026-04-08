# CLAUDE.md — claude_code_management_scripts

## What This Project Is

Tools and documentation for managing a large, long-lived Claude Code
installation. Born from 20 months of accumulated technical debt across 60+
projects.

## Current Status

**Phase:** Active development — foundational tooling in place, audit work ongoing.

**What's done:**
- Exit hook clearing permissions.allow on session end (installed globally)
- Bulk cleanup of 69 settings.local.json files
- Global gitignore protecting settings.local.json
- Token budget analysis and documentation
- TODO with prioritized findings

**What's next:** See `todo/TODO.md` — startup audit hook and MCP server scoping
are highest priority.

## Structure

```
hooks/          Hook scripts (canonical source; installed copies in ~/.claude/user_hook_scripts/)
scripts/        Standalone maintenance scripts
docs/           Reference documentation
todo/           TODO.md with prioritized work items
```

## Key Commands

```sh
# Run the cleanup hook manually against current project
~/.claude/user_hook_scripts/claude-settings-cleanup.sh

# Estimate token load for current project's CLAUDE.md chain
# (see docs/context-token-budget.md for the full script)

# Check global MCP servers
cat ~/.mcp.json | python3 -c "import json,sys; [print(k) for k in json.load(sys.stdin).get('mcpServers',{})]"

# View the TODO
cat todo/TODO.md
```

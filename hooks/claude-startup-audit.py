#!/usr/bin/env python3
"""
claude-startup-audit.py — SessionStart hook for Claude Code

Fires at session start. Walks the ancestor CLAUDE.md chain, checks .claude/*.md
files, inspects global and project MCP servers, and warns when startup context
load is high.

Injects a brief token budget summary into additionalContext so it appears at
the top of every session. Prints a systemMessage warning if over threshold.

Install:
  chmod +x ~/.claude/user_hook_scripts/claude-startup-audit.py

Register in ~/.claude/settings.json:
  {
    "hooks": {
      "SessionStart": [
        {
          "matcher": "",
          "hooks": [
            {
              "type": "command",
              "command": "/Users/mark/.claude/user_hook_scripts/claude-startup-audit.py"
            }
          ]
        }
      ]
    }
  }

Protocol: reads JSON from stdin, writes JSON to stdout, exits 0 always.
Never blocks session start — audit failures are silent.
"""

import json
import os
import sys
from pathlib import Path


# ── Thresholds ────────────────────────────────────────────────────────────────

# Warn if controllable startup tokens exceed this
WARN_TOKENS = 8_000

# Chars-per-token estimate (rough but consistent)
CHARS_PER_TOKEN = 4


# ── Helpers ───────────────────────────────────────────────────────────────────

def estimate_tokens(path: Path) -> int:
    try:
        return len(path.read_bytes()) // CHARS_PER_TOKEN
    except Exception:
        return 0


def find_ancestor_claude_mds(cwd: Path) -> list[tuple[Path, int]]:
    """Walk from cwd up to filesystem root, collect CLAUDE.md files and sizes.
    Also checks .claude/CLAUDE.md at each level. Returns list of (path, tokens).
    Mirrors the actual load order in Claude Code v2.1.94 (reversed ancestor walk).
    """
    dirs = []
    d = cwd
    while True:
        dirs.append(d)
        parent = d.parent
        if parent == d:
            break
        d = parent

    # reverse = root-to-cwd (actual load order)
    dirs.reverse()

    results = []
    for d in dirs:
        for candidate in [d / "CLAUDE.md", d / ".claude" / "CLAUDE.md"]:
            if candidate.exists() and candidate.is_file():
                results.append((candidate, estimate_tokens(candidate)))

    return results


def find_dot_claude_mds(cwd: Path) -> list[tuple[Path, int]]:
    """Files in .claude/ that auto-load (any .md, treated as rules if no paths: frontmatter).
    Excludes CLAUDE.md (already counted in ancestor walk).
    """
    dot_claude = cwd / ".claude"
    if not dot_claude.is_dir():
        return []

    results = []
    for f in sorted(dot_claude.glob("*.md")):
        if f.name.lower() != "claude.md":
            results.append((f, estimate_tokens(f)))

    # Also check .claude/rules/
    rules_dir = dot_claude / "rules"
    if rules_dir.is_dir():
        for f in sorted(rules_dir.rglob("*.md")):
            results.append((f, estimate_tokens(f)))

    return results


def find_user_claude_md() -> list[tuple[Path, int]]:
    """~/.claude/CLAUDE.md — user-level, loads for all projects."""
    p = Path.home() / ".claude" / "CLAUDE.md"
    if p.exists():
        return [(p, estimate_tokens(p))]
    return []


def load_mcp_servers(cwd: Path) -> tuple[list[str], list[str]]:
    """Return (global_servers, project_servers).
    Global: ~/.mcp.json
    Project: .mcp.json in cwd (the binary also walks ancestors but we report cwd).
    """
    def server_names(path: Path) -> list[str]:
        try:
            data = json.loads(path.read_text())
            return list(data.get("mcpServers", {}).keys())
        except Exception:
            return []

    global_servers = server_names(Path.home() / ".mcp.json")
    project_servers = server_names(cwd / ".mcp.json")
    return global_servers, project_servers


def mcp_ancestor_warning(cwd: Path) -> str | None:
    """Warn if a .mcp.json is being inherited from an ancestor (not cwd itself)."""
    if (cwd / ".mcp.json").exists():
        return None  # project has its own — no inheritance

    d = cwd.parent
    while True:
        candidate = d / ".mcp.json"
        if candidate.exists():
            return str(candidate)
        parent = d.parent
        if parent == d:
            break
        d = parent
    return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Read hook input
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        payload = {}

    cwd = Path(payload.get("cwd", os.getcwd()))
    session_id = payload.get("session_id", "unknown")
    source = payload.get("source", "startup")

    # ── Gather data ───────────────────────────────────────────────────────────

    user_mds = find_user_claude_md()
    ancestor_mds = find_ancestor_claude_mds(cwd)
    dot_claude_mds = find_dot_claude_mds(cwd)
    global_servers, project_servers = load_mcp_servers(cwd)
    inherited_mcp = mcp_ancestor_warning(cwd)

    # Deduplicate: user CLAUDE.md may appear in ancestor walk too
    user_md_paths = {p for p, _ in user_mds}
    ancestor_mds_deduped = [(p, t) for p, t in ancestor_mds if p not in user_md_paths]

    all_mds = user_mds + ancestor_mds_deduped + dot_claude_mds
    total_tokens = sum(t for _, t in all_mds)

    # ── Build report ──────────────────────────────────────────────────────────

    lines = []
    lines.append(f"── Startup Context Audit ({source}) ──")

    # CLAUDE.md chain
    if all_mds:
        lines.append(f"CLAUDE.md chain ({len(all_mds)} files, ~{total_tokens:,} tokens):")
        for p, t in all_mds:
            # Abbreviate home dir
            display = str(p).replace(str(Path.home()), "~")
            flag = " ⚠ LARGE" if t > 2_000 else ""
            lines.append(f"  {t:>5} tok  {display}{flag}")
    else:
        lines.append("CLAUDE.md chain: none found")

    # MCP servers
    if global_servers:
        lines.append(f"Global MCP servers (~/.mcp.json): {', '.join(global_servers)}")
    else:
        lines.append("Global MCP servers: none")

    if project_servers:
        lines.append(f"Project MCP servers (.mcp.json): {', '.join(project_servers)}")

    if inherited_mcp:
        display = inherited_mcp.replace(str(Path.home()), "~")
        lines.append(f"⚠ MCP inherited from ancestor: {display} (no local .mcp.json)")

    # Token warning
    warnings = []
    if total_tokens > WARN_TOKENS:
        warnings.append(
            f"High startup context: ~{total_tokens:,} tokens from CLAUDE.md files alone "
            f"(threshold: {WARN_TOKENS:,}). Consider trimming large files."
        )
    if inherited_mcp:
        warnings.append(
            f"MCP config inherited from {inherited_mcp.replace(str(Path.home()), '~')} "
            f"— add an empty .mcp.json here to stop ancestor walk."
        )
    if len(global_servers) >= 4:
        warnings.append(
            f"{len(global_servers)} global MCP servers load for every project "
            f"(~15-20k tokens). Consider scoping per-project."
        )

    summary = "\n".join(lines)
    if warnings:
        summary += "\n\nWARNINGS:\n" + "\n".join(f"  • {w}" for w in warnings)

    # ── Output ────────────────────────────────────────────────────────────────

    response = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": summary,
        },
        "continue": True,
        "suppressOutput": False,
    }

    # Only surface systemMessage if there are actual warnings
    if warnings:
        response["systemMessage"] = " | ".join(warnings)

    print(json.dumps(response))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Never crash a session start — fail silently
        print(json.dumps({"continue": True}))
        sys.exit(0)

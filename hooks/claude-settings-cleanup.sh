#!/usr/bin/env bash
# claude-settings-cleanup.sh
#
# Cleans up .claude/settings.local.json on Claude Code session exit.
#
# Strategy: wipe the entire permissions.allow list at the end of every session.
# Claude Code rebuilds it interactively as you approve things in the next
# session. Keeping stale allow entries is a security risk — especially one-shot
# accepted commands and anything that captured a credential inline.
#
# What is removed:
#   - ALL entries in permissions.allow (the whole list is cleared)
#
# What is preserved:
#   - permissions.deny  (explicit denials — intentional, keep them)
#   - enableAllProjectMcpServers
#   - enabledMcpjsonServers
#   - Any other keys (outputStyle, etc.)
#
# Usage:
#   Run directly:    claude-settings-cleanup.sh [path/to/settings.local.json]
#   As a hook:       configured in ~/.claude/settings.json (Stop hook)
#
# ── Installation on a new machine ────────────────────────────────────────────
#
#   1. Copy this directory to ~/.claude/user_hook_scripts/ and make it executable:
#        mkdir -p ~/.claude/user_hook_scripts
#        cp claude-settings-cleanup.sh ~/.claude/user_hook_scripts/
#        chmod +x ~/.claude/user_hook_scripts/claude-settings-cleanup.sh
#
#   2. Add the Stop hook to ~/.claude/settings.json:
#        {
#          "hooks": {
#            "Stop": [
#              {
#                "matcher": "",
#                "hooks": [
#                  {
#                    "type": "command",
#                    "command": "/Users/YOU/.claude/user_hook_scripts/claude-settings-cleanup.sh"
#                  }
#                ]
#              }
#            ]
#          }
#        }
#
#      Note: use an absolute path in the hook command — Claude Code does not
#      expand ~ in hook commands on all platforms.
#
#   3. That's it. The global hook fires for every project automatically.
#      No per-project setup needed.
#
# ── What this does NOT clean ─────────────────────────────────────────────────
#   - ~/.claude/settings.local.json  (your global allow list, if any)
#     If you want that cleaned too, add a second hook entry pointing at it:
#       "command": "/Users/YOU/.claude/user_hook_scripts/claude-settings-cleanup.sh /Users/YOU/.claude/settings.local.json"
#
# ── Dependencies ─────────────────────────────────────────────────────────────
#   - jq (brew install jq)
#
# ── Security note ────────────────────────────────────────────────────────────
#   Claude Code persists every tool-call permission you approve into this file.
#   That includes inline API keys, temp paths, and multi-line shell blobs.
#   Clearing allow on exit means the next session starts clean — you'll be
#   asked to approve things again, which is the intended security model.

set -euo pipefail

# ── Locate the settings file ──────────────────────────────────────────────────
if [[ $# -ge 1 ]]; then
    SETTINGS_FILE="$1"
else
    # Claude Code sets PWD to the project root when invoking Stop hooks
    SETTINGS_FILE="${PWD}/.claude/settings.local.json"
fi

if [[ ! -f "$SETTINGS_FILE" ]]; then
    exit 0
fi

if ! command -v jq &>/dev/null; then
    echo "claude-settings-cleanup: jq not found, skipping cleanup" >&2
    exit 0
fi

# ── Wipe permissions.allow, preserve everything else ─────────────────────────
CLEANED=$(jq '
  if .permissions then
    .permissions.allow = []
  else
    .
  end
' "$SETTINGS_FILE")

TMPFILE=$(mktemp "${SETTINGS_FILE}.XXXXXX")
echo "$CLEANED" > "$TMPFILE"
mv "$TMPFILE" "$SETTINGS_FILE"

echo "claude-settings-cleanup: cleared permissions.allow in $SETTINGS_FILE" >&2

#!/usr/bin/env bash
# install.sh — Install claude_code_management_scripts hooks on this machine.
#
# Safe to run multiple times (idempotent).
# Uses $HOME throughout — no hardcoded usernames.
#
# What this does:
#   1. Creates ~/.claude/scripts/ if needed
#   2. Symlinks all hooks from this repo into ~/.claude/scripts/
#   3. Patches ~/.claude/settings.json to wire the hooks
#   4. Checks dependencies and warns on anything missing
#
# Usage:
#   cd ~/path/to/claude_code_management_scripts
#   ./install.sh
#
# Uninstall:
#   Remove symlinks from ~/.claude/scripts/
#   Remove hook entries from ~/.claude/settings.json manually

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS_DIR="$HOME/.claude/scripts"
SETTINGS="$HOME/.claude/settings.json"

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  ✓${NC} $*"; }
warn() { echo -e "${YELLOW}  ⚠${NC} $*"; }
fail() { echo -e "${RED}  ✗${NC} $*"; }

echo ""
echo "claude_code_management_scripts — installer"
echo "==========================================="
echo "Repo:    $REPO_DIR"
echo "Scripts: $SCRIPTS_DIR"
echo "Settings: $SETTINGS"
echo ""

# ── Step 1: Check dependencies ────────────────────────────────────────────────
echo "Checking dependencies..."

if command -v jq &>/dev/null; then
    ok "jq found: $(which jq)"
else
    fail "jq not found — claude-settings-cleanup.sh requires it"
    echo "     Install: brew install jq"
    MISSING_JQ=1
fi

if command -v python3 &>/dev/null; then
    ok "python3 found: $(python3 --version)"
else
    fail "python3 not found — required for all Python hooks"
    exit 1
fi

if command -v uv &>/dev/null; then
    ok "uv found: $(uv --version)"
    USE_UV=1
else
    warn "uv not found — substrate hooks will use plain python3 (deps may be missing)"
    echo "     Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
    USE_UV=0
fi

if [[ -f "$HOME/bin/aifilter" ]]; then
    ok "aifilter found: $HOME/bin/aifilter"
else
    warn "aifilter not found at ~/bin/aifilter — prompt-ground.py will log warnings but not crash"
fi

if command -v ollama &>/dev/null; then
    ok "ollama found"
    if ollama list 2>/dev/null | grep -q "phi4"; then
        ok "phi4 model available"
    else
        warn "phi4 model not found in ollama — prompt-ground.py and autoground.py will fail gracefully"
        echo "     Install: ollama pull phi4"
    fi
else
    warn "ollama not found — prompt-ground.py and autoground.py will fail gracefully"
fi

SUBSTRATE="$HOME/Documents/src/file_metadata_and_embeddings"
if [[ -f "$SUBSTRATE/substrate_db.py" ]]; then
    ok "substrate_db found: $SUBSTRATE"
else
    warn "substrate_db.py not found at $SUBSTRATE — grounding hooks will skip DB queries"
fi

echo ""

# ── Step 2: Create scripts directory ─────────────────────────────────────────
echo "Setting up ~/.claude/scripts/ ..."
mkdir -p "$SCRIPTS_DIR"
ok "scripts dir ready: $SCRIPTS_DIR"
echo ""

# ── Step 3: Symlink hook scripts ──────────────────────────────────────────────
echo "Symlinking hooks..."

HOOKS=(
    "hooks/claude-settings-cleanup.sh"
    "hooks/claude-startup-audit.py"
    "hooks/prompt-ground.py"
)

for hook in "${HOOKS[@]}"; do
    src="$REPO_DIR/$hook"
    dst="$SCRIPTS_DIR/$(basename "$hook")"
    if [[ ! -f "$src" ]]; then
        fail "missing: $src"
        continue
    fi
    chmod +x "$src"
    # Remove existing symlink or copied file so we can place a clean symlink
    if [[ -e "$dst" || -L "$dst" ]]; then
        rm "$dst"
    fi
    ln -s "$src" "$dst"
    ok "linked: $dst → $src"
done

echo ""

# ── Step 4: Patch settings.json ───────────────────────────────────────────────
echo "Patching ~/.claude/settings.json ..."

if [[ ! -f "$SETTINGS" ]]; then
    warn "settings.json not found — creating minimal version"
    echo '{"hooks":{}}' > "$SETTINGS"
fi

# Build the hook entries with $HOME resolved.
# Grounding hooks (prompt-ground, autoground) run inside the substrate project
# venv via `uv run --project` so their imports and any future deps resolve correctly.
# Audit and cleanup have no project affinity — plain python3/bash is correct.
CLEANUP_CMD="$SCRIPTS_DIR/claude-settings-cleanup.sh"
AUDIT_CMD="python3 $SCRIPTS_DIR/claude-startup-audit.py"
if [[ "${USE_UV:-0}" -eq 1 && -f "$SUBSTRATE/pyproject.toml" ]]; then
    GROUND_CMD="uv run --project $SUBSTRATE python3 $SCRIPTS_DIR/prompt-ground.py"
    AUTOGROUND_CMD="uv run --project $SUBSTRATE python3 $SCRIPTS_DIR/autoground.py"
else
    GROUND_CMD="python3 $SCRIPTS_DIR/prompt-ground.py"
    AUTOGROUND_CMD="python3 $SCRIPTS_DIR/autoground.py"
fi

# Use python3 to merge hooks — safer than sed on JSON
python3 - "$SETTINGS" "$CLEANUP_CMD" "$AUDIT_CMD" "$GROUND_CMD" "$AUTOGROUND_CMD" << 'PYEOF'
import json, sys
from pathlib import Path

settings_path  = sys.argv[1]
cleanup_cmd    = sys.argv[2]
audit_cmd      = sys.argv[3]
ground_cmd     = sys.argv[4]
autoground_cmd = sys.argv[5]

settings = json.loads(Path(settings_path).read_text())
hooks = settings.setdefault("hooks", {})

def has_command(hook_list, cmd):
    for entry in hook_list:
        for h in entry.get("hooks", []):
            if h.get("command") == cmd:
                return True
    return False

def add_hook(event, cmd):
    event_hooks = hooks.setdefault(event, [{"matcher": "", "hooks": []}])
    if not has_command(event_hooks, cmd):
        event_hooks[0]["hooks"].append({"type": "command", "command": cmd})
        return True
    return False

changed = []
if add_hook("Stop",             cleanup_cmd):   changed.append(f"Stop: {cleanup_cmd}")
if add_hook("Stop",             autoground_cmd):changed.append(f"Stop: {autoground_cmd}")
if add_hook("SessionStart",     audit_cmd):     changed.append(f"SessionStart: {audit_cmd}")
if add_hook("UserPromptSubmit", ground_cmd):    changed.append(f"UserPromptSubmit: {ground_cmd}")

Path(settings_path).write_text(json.dumps(settings, indent=2))

for c in changed:
    print(f"  added: {c}")
if not changed:
    print("  all hooks already present — no changes needed")
PYEOF

ok "settings.json patched"
echo ""

# ── Step 5: Summary ───────────────────────────────────────────────────────────
echo "Installation complete."
echo ""
echo "Active hooks:"
echo "  SessionStart  → claude-startup-audit.py  (CLAUDE.md token audit)"
echo "  UserPromptSubmit → prompt-ground.py       (substrate DB grounding)"
echo "  Stop          → autoground.py             (write prior_art_notes.md)"
echo "  Stop          → claude-settings-cleanup.sh (clear permissions.allow)"
echo ""
echo "Logs:"
echo "  ~/.claude/logs/prompt-ground.log"
echo "  ~/.claude/logs/autoground.log"
echo ""

if [[ -n "${MISSING_JQ:-}" ]]; then
    warn "jq is missing — install it before the cleanup hook will work"
fi

echo "To verify: cat ~/.claude/settings.json | python3 -m json.tool"
echo ""

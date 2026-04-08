# Context Token Budget — What Loads at Claude Code Startup

Measured 2026-04-07 on a 20-month installation with 60+ projects.

## The Load Order

When Claude Code starts in a project directory, it loads context in this order:

1. **Claude Code system prompt** — fixed, ~10–15k tokens, not controllable
2. **CLAUDE.md ancestor chain** — every CLAUDE.md from `~` down to the project root
3. **`.claude/*.md` files** — any `.md` in the project's `.claude/` directory
4. **Skill/plugin SKILL.md files** — for each installed skill
5. **MCP server tool schemas** — for every server in `~/.mcp.json` + project `.mcp.json`
6. **Memory index** — `MEMORY.md` from the project's memory directory in `~/.claude/projects/`

## Measured Example: aifilter-project (2026-04-07)

| Source | Size | Est. Tokens | Controllable? |
|---|---|---|---|
| System prompt | — | ~12,000 | No |
| `~/CLAUDE.md` | 4.2KB | ~1,050 | Yes |
| `~/Documents/CLAUDE.md` | 2.4KB | ~600 | Yes |
| `~/Documents/src/My_AI_work/CLAUDE.md` | 0.5KB | ~120 | Yes |
| `aifilter-project/CLAUDE.md` | 20.2KB | ~5,050 | Yes |
| `.claude/CONTEXT_POLICY.md` | 3.4KB | ~850 | Yes |
| `.claude/CONTEXT-MANAGEMENT-GUIDE.md` | 11.6KB | ~2,900 | Yes |
| 5 global MCP servers (schemas) | — | ~15,000–20,000 | Yes |
| Skills system prompt | — | ~3,000–5,000 | Yes |
| Memory index | 0.2KB | ~50 | Yes |
| **Total (estimated)** | | **~40,000–47,000** | |

## What "50k tokens at startup" Means

A typical Claude model has a 200k token context window. 50k at startup means:
- ~25% of context is consumed before any work begins
- Long sessions with large file reads compound this quickly
- Tool call results (bash output, file reads) add to the running total
- In practice, useful working context is often 100–150k after fixed costs

## The Controllable Sources (and what to do)

### CLAUDE.md ancestor chain
Every directory from `~` to your project loads its CLAUDE.md. For a project
at `~/Documents/src/My_AI_work/project/`, that's 4 files minimum.

**Rules of thumb:**
- `~/CLAUDE.md` — keep under 2KB. Shell environment, not project inventory.
- `~/Documents/CLAUDE.md` — orientation only. Under 1KB ideally.
- Intermediate dirs — minimal or empty.
- Project CLAUDE.md — current state only. Target under 4KB.

### `.claude/*.md` files
Any `.md` placed in the `.claude/` directory auto-loads. This is easy to
abuse — long guides, architecture docs, and context policies all look
reasonable to put here, but every byte costs.

**Rule:** If it doesn't need to be in every session, don't put it in `.claude/`.

### MCP server schemas
Each MCP server injects its full tool schema. 5 servers can cost 15–20k tokens.

**Rule:** Global servers (`~/.mcp.json`) load for every project. Only put servers
here that are genuinely universal. Move project-specific servers to `.mcp.json`
in the project root.

### Skills / plugins
Each installed skill loads its SKILL.md. Some are large (32KB for skill-creator).
Skills load on demand in newer Claude Code versions — verify this before auditing.

## Measuring Your Own Budget

```sh
# Estimate tokens from CLAUDE.md chain for current project
# (run from project root)
dir="$PWD"
total=0
while [[ "$dir" != "/" ]]; do
    f="$dir/CLAUDE.md"
    if [[ -f "$f" ]]; then
        chars=$(wc -c < "$f")
        tokens=$(( chars / 4 ))
        echo "$tokens tokens  $f"
        total=$(( total + tokens ))
    fi
    dir=$(dirname "$dir")
done
# Also check home
f="$HOME/CLAUDE.md"
if [[ -f "$f" ]]; then
    chars=$(wc -c < "$f")
    tokens=$(( chars / 4 ))
    echo "$tokens tokens  $f"
    total=$(( total + tokens ))
fi
echo "---"
echo "Total CLAUDE.md chain: ~$total tokens"

# Check .claude/*.md files
echo ""
echo ".claude/*.md files:"
for f in .claude/*.md; do
    [[ -f "$f" ]] && chars=$(wc -c < "$f") && echo "  $(( chars / 4 )) tokens  $f"
done

# Check global MCP servers
echo ""
echo "Global MCP servers:"
cat ~/.mcp.json 2>/dev/null | python3 -c "import json,sys; [print(' ', k) for k in json.load(sys.stdin).get('mcpServers',{})]"
```

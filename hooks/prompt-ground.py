#!/usr/bin/env python3
"""
prompt-ground.py — Claude Code UserPromptSubmit hook: prompt grounding.

Fires before each prompt reaches the model. Extracts intent keywords from
the prompt, queries the substrate DB for matching prior work, and injects
matching nodes as additionalContext so the model starts informed.

Hook event: UserPromptSubmit
Input:  JSON from stdin — {hook_event_name, prompt, session_id, cwd}
Output: JSON to stdout — {hookEventName: "UserPromptSubmit", additionalContext: "..."}

The model sees the injected context as session context before answering.
The user's prompt is not modified.

Requires:
  - substrate_db.py + autoground_query.py in SUBSTRATE_DIR (see config below)
  - aifilter in ~/bin/aifilter
  - behavior: keyword_extract.txt in ~/.config/aifilter/behaviors/
  - phi4 available in Ollama

Self-identifying on failure:
  - All errors exit 0 with empty additionalContext — session never blocked
  - Failures logged to ~/.claude/logs/prompt-ground.log
"""

import json
import logging
import os
import subprocess
import sys
import traceback
from pathlib import Path

# --- config (uses HOME, not hardcoded paths) ---
HOME = Path.home()
SUBSTRATE_DIR = HOME / "src" / "file_metadata_and_embeddings"
AIFILTER      = HOME / "bin" / "aifilter"
MODEL         = "phi4"
TOP_K         = 8
MIN_KEYWORDS  = 2
LOG_FILE      = HOME / ".claude" / "logs" / "prompt-ground.log"
HOOK_ID       = "[prompt-ground hook — ~/.claude/scripts/prompt-ground.py]"

sys.path.insert(0, str(SUBSTRATE_DIR))

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("prompt-ground")


def _empty_response() -> str:
    return json.dumps({
        "hookEventName": "UserPromptSubmit",
        "additionalContext": "",
    })


def extract_keywords(prompt: str) -> list[str]:
    """Extract intent keywords from the prompt via phi4."""
    try:
        result = subprocess.run(
            [str(AIFILTER), "-b", "keyword_extract", "-m", MODEL],
            input=prompt, capture_output=True, text=True, timeout=20
        )
        if result.returncode != 0:
            return []
        keywords = result.stdout.strip().split()
        return [k for k in keywords if len(k) > 2]
    except Exception:
        return []


def format_context(nodes: list[dict]) -> str:
    """Format matching nodes as terse prior-work context."""
    if not nodes:
        return ""
    lines = ["## Prior Work (autoground)"]
    for n in nodes:
        label  = n.get("label", "unknown")
        source = n.get("source", "")
        ntype  = n.get("type", "")
        seen   = n.get("last_seen", "")[:10]  # date only
        if source:
            lines.append(f"- [{label}]({source}) ({ntype}, {seen})")
        else:
            lines.append(f"- {label} ({ntype}, {seen})")
    return "\n".join(lines)


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        print(_empty_response())
        sys.exit(0)

    prompt = payload.get("prompt", "").strip()
    if not prompt:
        print(_empty_response())
        sys.exit(0)

    # Extract keywords
    keywords = extract_keywords(prompt)
    if len(keywords) < MIN_KEYWORDS:
        log.info("too few keywords (%d) for prompt: %s", len(keywords), prompt[:60])
        print(_empty_response())
        sys.exit(0)

    # Query substrate DB
    try:
        from autoground_query import query  # noqa: PLC0415
        nodes = query(keywords, top_k=TOP_K)
    except Exception as exc:
        log.warning("DB query failed: %s", exc)
        print(_empty_response())
        sys.exit(0)

    if not nodes:
        log.info("no matches for keywords: %s", keywords[:5])
        print(_empty_response())
        sys.exit(0)

    context = format_context(nodes)
    log.info("grounded prompt with %d nodes, keywords: %s", len(nodes), keywords[:5])

    print(json.dumps({
        "hookEventName": "UserPromptSubmit",
        "additionalContext": context,
    }))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log.error("unhandled exception: %s\n%s", exc, traceback.format_exc())
        print(_empty_response())
        sys.exit(0)

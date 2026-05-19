"""Append-only gate decision log.

Each gate-bearing tool (score_ambiguity, analyze_verify_failure, run_verify,
track_manual_checks) appends one JSON line per call to
`<project_root>/.contractfirst/gates.jsonl` so a human can grep the history of
decisions the AI hit during a session. Best-effort: never raises.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

GATES_FILENAME = "gates.jsonl"


def append_gate_event(project_root: str | Path, tool: str, decision: dict[str, Any]) -> str | None:
    try:
        root = Path(project_root).resolve()
        if not root.is_dir():
            return None
        log_dir = root / ".contractfirst"
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / GATES_FILENAME
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "tool": tool,
            "decision": decision,
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return str(path)
    except (OSError, TypeError, ValueError):
        return None

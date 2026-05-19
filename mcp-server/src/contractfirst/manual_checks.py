"""track_manual_checks: declare and confirm manual verification items per feature.

Manual checks (visual layout, interaction feel, focus order, playtest) cannot
be automated by `run_verify`. Without a ledger, a green `verify.sh` looks
like "done" even though the SKILL.md Verify Gate says it is not for ui-heavy
or mixed projects. This tool persists a per-feature ledger that `run_verify`
consults to gate `overall: pass`.

Storage layout (under <project_root>/.contractfirst/manual-checks/):
    <feature>.json   one ledger file per feature slug

Schema (per file):
    {
      "feature": "minigame-ui",
      "created_at": "2026-05-12T10:00:00",
      "checks": [
        {
          "id": "V1",
          "description": "ProximityPrompt 3x → only one UI",
          "required": true,
          "status": "pending" | "confirmed" | "handed_off",
          "confirmed_at": "2026-05-12T10:30:00" | null,
          "note": "playtest 3 min @ 1080p" | null
        }
      ]
    }
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .gatelog import append_gate_event

VALID_OPS = ("declare", "confirm", "handoff", "list", "summary")
VALID_STATUSES = ("pending", "confirmed", "handed_off")
FEATURE_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _ledger_dir(root: Path) -> Path:
    return root / ".contractfirst" / "manual-checks"


def _ledger_path(root: Path, feature: str) -> Path:
    return _ledger_dir(root) / f"{feature}.json"


def _validate_feature(feature: str) -> None:
    if not isinstance(feature, str) or not FEATURE_SLUG_RE.match(feature):
        raise ValueError(
            f"feature must be a slug [A-Za-z0-9._-]{{1,64}}; got {feature!r}"
        )


def _read_ledger(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_ledger(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _summary(checks: list[dict[str, Any]]) -> dict[str, Any]:
    required = [c for c in checks if c.get("required", True)]
    confirmed = [c for c in required if c["status"] == "confirmed"]
    handed_off = [c for c in required if c["status"] == "handed_off"]
    pending = [c for c in required if c["status"] == "pending"]
    optional = [c for c in checks if not c.get("required", True)]
    all_required_resolved = len(pending) == 0
    return {
        "total": len(checks),
        "required": len(required),
        "optional": len(optional),
        "confirmed": len(confirmed),
        "handed_off": len(handed_off),
        "pending": len(pending),
        "all_required_resolved": all_required_resolved,
        "pending_ids": [c["id"] for c in pending],
    }


def _declare(
    path: Path,
    feature: str,
    checks: list[dict[str, Any]],
    replace: bool,
) -> dict[str, Any]:
    if not isinstance(checks, list) or not checks:
        raise ValueError("checks must be a non-empty list")
    existing = _read_ledger(path) if not replace else None
    seen_ids: set[str] = set()
    if existing:
        seen_ids = {c["id"] for c in existing.get("checks", [])}
    new_entries: list[dict[str, Any]] = []
    for raw in checks:
        if not isinstance(raw, dict):
            raise ValueError(f"each check must be a dict, got {type(raw).__name__}")
        check_id = raw.get("id")
        description = raw.get("description")
        if not isinstance(check_id, str) or not check_id.strip():
            raise ValueError("check 'id' must be a non-empty string")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"check {check_id!r} 'description' must be a non-empty string")
        if check_id in seen_ids:
            raise ValueError(f"duplicate check id: {check_id!r}")
        seen_ids.add(check_id)
        required = bool(raw.get("required", True))
        new_entries.append(
            {
                "id": check_id,
                "description": description,
                "required": required,
                "status": "pending",
                "confirmed_at": None,
                "note": None,
            }
        )

    if existing and not replace:
        existing["checks"].extend(new_entries)
        data = existing
    else:
        data = {
            "feature": feature,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "checks": new_entries,
        }
    _write_ledger(path, data)
    return data


def _set_status(
    path: Path,
    check_id: str,
    new_status: str,
    note: str | None,
) -> dict[str, Any]:
    data = _read_ledger(path)
    if data is None:
        raise ValueError(f"no manual-check ledger at {path}; call declare first")
    for check in data["checks"]:
        if check["id"] == check_id:
            check["status"] = new_status
            check["confirmed_at"] = datetime.now().isoformat(timespec="seconds")
            if note is not None:
                check["note"] = note
            _write_ledger(path, data)
            return data
    raise ValueError(f"check id {check_id!r} not found in ledger")


def track_manual_checks(
    project_root: str,
    feature: str,
    op: str = "summary",
    checks: list[dict[str, Any]] | None = None,
    check_id: str | None = None,
    note: str | None = None,
    replace: bool = False,
) -> dict[str, Any]:
    """Declare or confirm manual verification items for a feature.

    Operations:
      - declare: create/append checks (each: id, description, required?).
      - confirm: mark a check as confirmed by the human.
      - handoff: mark a check as explicitly handed off (still counts as resolved).
      - list:    return the full ledger.
      - summary: return only the summary block.

    Raises ValueError on invalid input. Best-effort gate-log entry is appended
    on every call.
    """
    if op not in VALID_OPS:
        raise ValueError(f"op must be one of {VALID_OPS}, got {op!r}")
    _validate_feature(feature)
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise ValueError(f"project_root is not a directory: {project_root}")

    path = _ledger_path(root, feature)

    if op == "declare":
        data = _declare(path, feature, checks or [], replace=replace)
    elif op == "confirm":
        if not check_id:
            raise ValueError("confirm requires check_id")
        data = _set_status(path, check_id, "confirmed", note)
    elif op == "handoff":
        if not check_id:
            raise ValueError("handoff requires check_id")
        data = _set_status(path, check_id, "handed_off", note)
    else:  # list, summary
        data = _read_ledger(path) or {
            "feature": feature,
            "created_at": None,
            "checks": [],
        }

    summary = _summary(data["checks"])
    result: dict[str, Any] = {
        "feature": feature,
        "op": op,
        "ledger_path": str(path),
        "summary": summary,
    }
    if op != "summary":
        result["checks"] = data["checks"]

    append_gate_event(
        root,
        "track_manual_checks",
        {
            "feature": feature,
            "op": op,
            "check_id": check_id,
            "all_required_resolved": summary["all_required_resolved"],
            "pending_ids": summary["pending_ids"],
        },
    )
    return result


def read_summary(project_root: str | Path, feature: str) -> dict[str, Any] | None:
    """Helper used by run_verify; returns the summary block or None if no ledger."""
    try:
        _validate_feature(feature)
    except ValueError:
        return None
    root = Path(project_root).resolve()
    data = _read_ledger(_ledger_path(root, feature))
    if data is None:
        return None
    return _summary(data["checks"])

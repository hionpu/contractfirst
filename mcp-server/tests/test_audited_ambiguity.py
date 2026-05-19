"""Tests for the audited two-step ambiguity gate.

Covers: draft creation, auditor-prompt content, verdict parsing (happy path,
rejection, schema invalid, token mismatch, JSON wrapped in markdown fences),
draft expiry, draft cap, gates.jsonl emission, single-shot consumption.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from contractfirst import ambiguity
from contractfirst.ambiguity import (
    AUDIT_TOKEN_BYTES,
    DRAFT_CAP_PER_PROJECT,
    DRAFT_TTL_HOURS,
    commit_ambiguity_audit,
    draft_ambiguity_score,
)

USER_PROMPT = (
    "Implement a login feature. It must use OAuth, and verify by checking "
    "the user can sign in with Google."
)


def _good_draft(project_root: str, **overrides):
    kwargs = dict(
        project_root=project_root,
        user_prompt_verbatim=USER_PROMPT,
        goal_clarity=0.9,
        goal_evidence="Implement a login feature",
        constraint_clarity=0.8,
        constraint_evidence="must use OAuth",
        success_criteria_clarity=0.85,
        success_evidence="user can sign in with Google",
        blocking_questions=[],
        open_questions=None,
    )
    kwargs.update(overrides)
    return draft_ambiguity_score(**kwargs)


def _verdict_json(audit_token: str, *, goal=True, constraint=True, success=True) -> str:
    return json.dumps({
        "audit_token": audit_token,
        "dimensions": {
            "goal":       {"valid": goal,       "reason": "matches request"},
            "constraint": {"valid": constraint, "reason": "matches request"},
            "success":    {"valid": success,    "reason": "matches request"},
        },
    })


# ── draft_ambiguity_score ───────────────────────────────────────────


def test_draft_creates_file_with_token_and_prompt(tmp_path: Path):
    res = _good_draft(str(tmp_path))
    assert "draft_id" in res
    assert len(res["draft_id"]) == 12
    assert "audit_token" in res
    assert res["audit_token"]
    # auditor prompt should contain the token and the user prompt
    prompt = res["auditor_prompt_markdown"]
    assert res["audit_token"] in prompt
    assert USER_PROMPT in prompt
    # draft file should exist
    draft_path = tmp_path / ".contractfirst" / "drafts" / f"{res['draft_id']}.json"
    assert draft_path.is_file()
    saved = json.loads(draft_path.read_text(encoding="utf-8"))
    assert saved["audit_token"] == res["audit_token"]
    assert saved["claims"]["goal"]["score"] == 0.9


def test_draft_rejects_short_user_prompt(tmp_path: Path):
    with pytest.raises(ValueError, match="user_prompt_verbatim"):
        _good_draft(str(tmp_path), user_prompt_verbatim="hi")


def test_draft_rejects_inflated_none_score(tmp_path: Path):
    # The legacy "none → score <= 0.30" rule still applies in the draft phase
    with pytest.raises(ValueError, match="0.30"):
        _good_draft(
            str(tmp_path),
            constraint_clarity=0.9,
            constraint_evidence="none",
        )


def test_draft_logs_to_gates_jsonl(tmp_path: Path):
    _good_draft(str(tmp_path))
    gates = tmp_path / ".contractfirst" / "gates.jsonl"
    assert gates.is_file()
    line = gates.read_text(encoding="utf-8").strip().splitlines()[-1]
    entry = json.loads(line)
    assert entry["tool"] == "draft_ambiguity_score"
    assert "draft_id" in entry["decision"]


def test_draft_cap_purges_oldest(tmp_path: Path):
    # Create CAP+5 drafts; oldest 5 should be purged
    drafts_dir = tmp_path / ".contractfirst" / "drafts"
    extra = 5
    ids: list[str] = []
    for i in range(DRAFT_CAP_PER_PROJECT + extra):
        res = _good_draft(str(tmp_path))
        ids.append(res["draft_id"])
        # Ensure distinct mtimes
        path = drafts_dir / f"{res['draft_id']}.json"
        # Set an artificially old mtime for the first `extra` drafts so they get purged
        if i < extra:
            old = time.time() - 3600 * 2  # 2h ago, past TTL
            os.utime(path, (old, old))
    remaining = list(drafts_dir.glob("*.json"))
    assert len(remaining) <= DRAFT_CAP_PER_PROJECT


def test_draft_expired_purged_on_next_call(tmp_path: Path):
    # Create a draft, age it past TTL, create a second draft — first should be gone
    res1 = _good_draft(str(tmp_path))
    path1 = tmp_path / ".contractfirst" / "drafts" / f"{res1['draft_id']}.json"
    old = time.time() - 3600 * (DRAFT_TTL_HOURS + 1)
    os.utime(path1, (old, old))
    _good_draft(str(tmp_path))
    assert not path1.is_file(), "expired draft should have been purged"


# ── commit_ambiguity_audit ──────────────────────────────────────────


def test_commit_happy_path_all_valid(tmp_path: Path):
    drafted = _good_draft(str(tmp_path))
    transcript = f"Auditor reply:\n{_verdict_json(drafted['audit_token'])}"
    res = commit_ambiguity_audit(
        project_root=str(tmp_path),
        draft_id=drafted["draft_id"],
        auditor_transcript=transcript,
    )
    assert res["proceed"] is True
    assert res["rejected_dimensions"] == []
    assert res["final_scores"]["goal"] == 0.9
    # Draft consumed
    draft_path = tmp_path / ".contractfirst" / "drafts" / f"{drafted['draft_id']}.json"
    assert not draft_path.is_file()


def test_commit_rejection_forces_zero(tmp_path: Path):
    drafted = _good_draft(str(tmp_path))
    transcript = _verdict_json(drafted["audit_token"], constraint=False)
    res = commit_ambiguity_audit(
        project_root=str(tmp_path),
        draft_id=drafted["draft_id"],
        auditor_transcript=transcript,
    )
    assert res["final_scores"]["constraint"] == 0.0
    assert "constraint" in res["rejected_dimensions"]
    # constraint contributed 0.30 * 0.8 = 0.24 originally; losing it → ambiguity rises
    assert res["ambiguity"] > 0.20
    assert res["proceed"] is False


def test_commit_wrong_token_rejected_and_keeps_draft(tmp_path: Path):
    drafted = _good_draft(str(tmp_path))
    transcript = _verdict_json("WRONG_TOKEN_XYZ")
    res = commit_ambiguity_audit(
        project_root=str(tmp_path),
        draft_id=drafted["draft_id"],
        auditor_transcript=transcript,
    )
    assert res["proceed"] is False
    assert res["error"] == "verdict_token_mismatch"
    # Draft NOT consumed — Agent A may retry
    draft_path = tmp_path / ".contractfirst" / "drafts" / f"{drafted['draft_id']}.json"
    assert draft_path.is_file()


def test_commit_malformed_json_rejected(tmp_path: Path):
    drafted = _good_draft(str(tmp_path))
    transcript = "Auditor says: yes looks good. (no JSON)"
    res = commit_ambiguity_audit(
        project_root=str(tmp_path),
        draft_id=drafted["draft_id"],
        auditor_transcript=transcript,
    )
    assert res["error"] == "verdict_token_mismatch"


def test_commit_schema_invalid_rejected(tmp_path: Path):
    drafted = _good_draft(str(tmp_path))
    bad = json.dumps({
        "audit_token": drafted["audit_token"],
        "dimensions": {"goal": "yes"},  # not a dict, missing keys
    })
    res = commit_ambiguity_audit(
        project_root=str(tmp_path),
        draft_id=drafted["draft_id"],
        auditor_transcript=bad,
    )
    assert res["error"] == "verdict_schema_invalid"


def test_commit_missing_draft_rejected(tmp_path: Path):
    res = commit_ambiguity_audit(
        project_root=str(tmp_path),
        draft_id="nonexistent12",
        auditor_transcript=_verdict_json("anytoken"),
    )
    assert res["error"] == "draft_not_found"


def test_commit_extracts_json_from_markdown_fence(tmp_path: Path):
    drafted = _good_draft(str(tmp_path))
    transcript = (
        "Auditor verdict below:\n\n"
        "```json\n"
        f"{_verdict_json(drafted['audit_token'])}\n"
        "```\n"
        "(end of audit)\n"
    )
    res = commit_ambiguity_audit(
        project_root=str(tmp_path),
        draft_id=drafted["draft_id"],
        auditor_transcript=transcript,
    )
    assert res["proceed"] is True


def test_commit_handles_nested_objects_in_reason(tmp_path: Path):
    drafted = _good_draft(str(tmp_path))
    # reason fields may legitimately contain quotes / braces; ensure the parser
    # finds the right outermost object.
    transcript = json.dumps({
        "audit_token": drafted["audit_token"],
        "dimensions": {
            "goal":       {"valid": True,  "reason": "ok (paren) and {brace} chars"},
            "constraint": {"valid": True,  "reason": "ok"},
            "success":    {"valid": True,  "reason": "ok"},
        },
    })
    res = commit_ambiguity_audit(
        project_root=str(tmp_path),
        draft_id=drafted["draft_id"],
        auditor_transcript=transcript,
    )
    assert res["proceed"] is True


def test_commit_logs_to_gates_jsonl(tmp_path: Path):
    drafted = _good_draft(str(tmp_path))
    commit_ambiguity_audit(
        project_root=str(tmp_path),
        draft_id=drafted["draft_id"],
        auditor_transcript=_verdict_json(drafted["audit_token"]),
    )
    gates = (tmp_path / ".contractfirst" / "gates.jsonl").read_text(encoding="utf-8")
    lines = [json.loads(l) for l in gates.strip().splitlines()]
    tools = [l["tool"] for l in lines]
    assert "draft_ambiguity_score" in tools
    assert "commit_ambiguity_audit" in tools
    commit_entry = [l for l in lines if l["tool"] == "commit_ambiguity_audit"][-1]
    assert commit_entry["decision"]["proceed"] is True


def test_commit_blocking_questions_block_proceed(tmp_path: Path):
    drafted = _good_draft(str(tmp_path), blocking_questions=["which oauth provider?"])
    res = commit_ambiguity_audit(
        project_root=str(tmp_path),
        draft_id=drafted["draft_id"],
        auditor_transcript=_verdict_json(drafted["audit_token"]),
    )
    # All dims valid but blocking_count > 0 → cannot proceed
    assert res["proceed"] is False
    assert res["blocking_count"] == 1


def test_commit_idempotent_after_success_returns_not_found(tmp_path: Path):
    drafted = _good_draft(str(tmp_path))
    transcript = _verdict_json(drafted["audit_token"])
    first = commit_ambiguity_audit(
        project_root=str(tmp_path),
        draft_id=drafted["draft_id"],
        auditor_transcript=transcript,
    )
    assert first["proceed"] is True
    # Second call with same draft_id should fail — draft consumed
    second = commit_ambiguity_audit(
        project_root=str(tmp_path),
        draft_id=drafted["draft_id"],
        auditor_transcript=transcript,
    )
    assert second["error"] == "draft_not_found"

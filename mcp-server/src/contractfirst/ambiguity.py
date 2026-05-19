"""Ambiguity gate tools.

Three tools, in increasing strength:

1. score_ambiguity (legacy / single-call): Agent A self-scores with evidence
   quotes. Cheap. Detects fabrication via the "none" + min-length rules but
   still trusts Agent A to be honest about its own evidence.

2. draft_ambiguity_score → commit_ambiguity_audit (audited two-step):
   Agent A submits scores + evidence as a draft. MCP returns an auditor
   prompt + audit_token. Agent A must dispatch a sub-agent (CLI-native:
   Task tool / pi -p / codex exec / etc.) with that prompt, then return the
   sub-agent's verbatim transcript. MCP parses the verdict, forces rejected
   dimensions to 0.0, and recomputes. Tampering surfaces in gates.jsonl.

Weights and threshold are shared across all three tools.
"""

from __future__ import annotations

import json
import re
import secrets
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .gatelog import append_gate_event

W_GOAL = 0.40
W_CONSTRAINT = 0.30
W_SUCCESS = 0.30
AMBIGUITY_THRESHOLD = 0.20
MIN_EVIDENCE_LEN = 8
NONE_TOKEN = "none"

DRAFT_DIR_REL = ".contractfirst/drafts"
DRAFT_TTL_HOURS = 1
DRAFT_CAP_PER_PROJECT = 50
AUDIT_TOKEN_BYTES = 12  # ~16 url-safe chars
MIN_USER_PROMPT_LEN = 8


def _validate_score(name: str, value: float) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{name} must be a number, got {type(value).__name__}")
    if value < 0.0 or value > 1.0:
        raise ValueError(f"{name} must be in [0.0, 1.0], got {value}")


def _validate_evidence(name: str, evidence: str, score: float) -> None:
    if not isinstance(evidence, str):
        raise ValueError(f"{name} must be a string, got {type(evidence).__name__}")
    stripped = evidence.strip()
    if not stripped:
        raise ValueError(
            f"{name} must be a non-empty quote from the user's request, "
            f"or the literal token {NONE_TOKEN!r} to indicate the user said nothing"
        )
    if stripped.lower() == NONE_TOKEN:
        # "none" means: user said nothing → score must be low (<= 0.3).
        if score > 0.3:
            raise ValueError(
                f"{name} evidence is 'none' but score is {score:.2f} > 0.30; "
                f"a missing-evidence dimension cannot be scored as clear"
            )
        return
    if len(stripped) < MIN_EVIDENCE_LEN:
        raise ValueError(
            f"{name} must be at least {MIN_EVIDENCE_LEN} characters of verbatim quote "
            f"(or {NONE_TOKEN!r}); got {stripped!r}"
        )


def _truncate(text: str, limit: int = 200) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _build_report(
    goal: float,
    constraint: float,
    success: float,
    goal_ev: str,
    constraint_ev: str,
    success_ev: str,
    w_goal: float,
    w_constraint: float,
    w_success: float,
    total_clarity: float,
    ambiguity: float,
    blocking_questions: list[str],
    open_questions: list[str],
    proceed: bool,
) -> str:
    lines = [
        "Ambiguity Report",
        f"- Goal clarity: {goal:.2f} × {W_GOAL:.2f} = {w_goal:.2f}",
        f"  evidence: {_truncate(goal_ev)}",
        f"- Constraint clarity: {constraint:.2f} × {W_CONSTRAINT:.2f} = {w_constraint:.2f}",
        f"  evidence: {_truncate(constraint_ev)}",
        f"- Success criteria clarity: {success:.2f} × {W_SUCCESS:.2f} = {w_success:.2f}",
        f"  evidence: {_truncate(success_ev)}",
        f"- Total clarity: {total_clarity:.2f}",
        f"- Ambiguity (1 - clarity): {ambiguity:.2f}",
        f"- Blocking questions: {len(blocking_questions)}",
        f"- Open questions: {len(open_questions)}",
        f"- Proceed: {'YES' if proceed else 'NO'} "
        f"(threshold {AMBIGUITY_THRESHOLD:.2f}, blocking must be 0)",
    ]
    if blocking_questions:
        lines.append("")
        lines.append("Blocking questions:")
        for q in blocking_questions:
            lines.append(f"  - {q}")
    if open_questions:
        lines.append("")
        lines.append("Open questions:")
        for q in open_questions:
            lines.append(f"  - {q}")
    return "\n".join(lines)


def score_ambiguity(
    goal_clarity: float,
    goal_evidence: str,
    constraint_clarity: float,
    constraint_evidence: str,
    success_criteria_clarity: float,
    success_evidence: str,
    blocking_questions: list[str],
    open_questions: list[str] | None = None,
    project_root: str | None = None,
) -> dict[str, Any]:
    """Compute the ambiguity gate verdict from clarity scores + required evidence.

    Each clarity score in [0.0, 1.0] must be paired with a verbatim quote from
    the user's request (>= 8 chars), or the literal string "none" if the user
    said nothing about that dimension. "none" forces the score to be <= 0.30,
    so the AI cannot claim high clarity without producing evidence. The
    deterministic weighted sum is unchanged: ambiguity = 1 - (0.4*goal +
    0.3*constraint + 0.3*success). proceed=true requires ambiguity <= 0.20
    AND zero blocking questions.
    """
    _validate_score("goal_clarity", goal_clarity)
    _validate_score("constraint_clarity", constraint_clarity)
    _validate_score("success_criteria_clarity", success_criteria_clarity)
    _validate_evidence("goal_evidence", goal_evidence, goal_clarity)
    _validate_evidence("constraint_evidence", constraint_evidence, constraint_clarity)
    _validate_evidence("success_evidence", success_evidence, success_criteria_clarity)
    if not isinstance(blocking_questions, list):
        raise ValueError("blocking_questions must be a list of strings")
    open_qs = list(open_questions) if open_questions else []
    if not isinstance(open_qs, list):
        raise ValueError("open_questions must be a list of strings")

    w_goal = goal_clarity * W_GOAL
    w_constraint = constraint_clarity * W_CONSTRAINT
    w_success = success_criteria_clarity * W_SUCCESS
    total_clarity = w_goal + w_constraint + w_success
    ambiguity = 1.0 - total_clarity
    proceed = ambiguity <= AMBIGUITY_THRESHOLD and len(blocking_questions) == 0

    result = {
        "scores": {
            "goal_clarity": round(goal_clarity, 2),
            "constraint_clarity": round(constraint_clarity, 2),
            "success_criteria_clarity": round(success_criteria_clarity, 2),
        },
        "evidence": {
            "goal": goal_evidence.strip(),
            "constraint": constraint_evidence.strip(),
            "success": success_evidence.strip(),
        },
        "weighted": {
            "goal": round(w_goal, 2),
            "constraint": round(w_constraint, 2),
            "success": round(w_success, 2),
        },
        "total_clarity": round(total_clarity, 2),
        "ambiguity": ambiguity,
        "blocking_count": len(blocking_questions),
        "open_question_count": len(open_qs),
        "proceed": proceed,
        "report_markdown": _build_report(
            goal_clarity,
            constraint_clarity,
            success_criteria_clarity,
            goal_evidence.strip(),
            constraint_evidence.strip(),
            success_evidence.strip(),
            w_goal,
            w_constraint,
            w_success,
            total_clarity,
            ambiguity,
            list(blocking_questions),
            open_qs,
            proceed,
        ),
    }

    if project_root:
        append_gate_event(
            project_root,
            "score_ambiguity",
            {
                "proceed": proceed,
                "ambiguity": round(ambiguity, 4),
                "blocking_count": len(blocking_questions),
                "evidence_lengths": {
                    "goal": len(goal_evidence.strip()),
                    "constraint": len(constraint_evidence.strip()),
                    "success": len(success_evidence.strip()),
                },
            },
        )
    return result


# ─────────────────────────────────────────────────────────────────
# Audited two-step: draft_ambiguity_score → commit_ambiguity_audit
# ─────────────────────────────────────────────────────────────────


def _drafts_dir(project_root: str) -> Path:
    return Path(project_root).resolve() / DRAFT_DIR_REL


def _purge_old_drafts(drafts_dir: Path) -> None:
    """Delete drafts older than TTL; cap remaining at DRAFT_CAP_PER_PROJECT."""
    if not drafts_dir.is_dir():
        return
    cutoff = datetime.now() - timedelta(hours=DRAFT_TTL_HOURS)
    try:
        drafts = list(drafts_dir.glob("*.json"))
    except OSError:
        return
    for p in drafts:
        try:
            if datetime.fromtimestamp(p.stat().st_mtime) < cutoff:
                p.unlink()
        except OSError:
            continue
    try:
        remaining = sorted(drafts_dir.glob("*.json"), key=lambda x: x.stat().st_mtime)
    except OSError:
        return
    excess = len(remaining) - DRAFT_CAP_PER_PROJECT
    for p in remaining[:max(0, excess)]:
        try:
            p.unlink()
        except OSError:
            continue


def _build_auditor_prompt(
    user_prompt: str,
    claims: dict[str, dict[str, Any]],
    audit_token: str,
) -> str:
    g = claims["goal"]
    c = claims["constraint"]
    s = claims["success"]
    return (
        "You are the Auditor for an ambiguity gate. Decide whether each evidence "
        "quote Agent A submitted is a legitimate verbatim quote from the user's "
        "original request, or a fabrication / paraphrase / forced reading.\n\n"
        "USER'S ORIGINAL REQUEST (verbatim):\n"
        '"""\n'
        f"{user_prompt}\n"
        '"""\n\n'
        "AGENT A's CLAIMS:\n"
        f"- goal:       score={g['score']:.2f}  evidence={g['evidence']!r}\n"
        f"- constraint: score={c['score']:.2f}  evidence={c['evidence']!r}\n"
        f"- success:    score={s['score']:.2f}  evidence={s['evidence']!r}\n\n"
        "For each dimension, decide:\n"
        '- valid=true  → evidence is verbatim (or "none" is honest — the user '
        "really said nothing about that dimension)\n"
        "- valid=false → evidence is fabricated, paraphrased, or a forced "
        'reading; OR scored high while evidence is "none"\n\n'
        "OUTPUT FORMAT — JSON only, no prose, no markdown fence. "
        "Echo the audit_token verbatim:\n\n"
        "{\n"
        f'  "audit_token": "{audit_token}",\n'
        '  "dimensions": {\n'
        '    "goal":       {"valid": true,  "reason": "..."},\n'
        '    "constraint": {"valid": false, "reason": "..."},\n'
        '    "success":    {"valid": true,  "reason": "..."}\n'
        "  }\n"
        "}\n\n"
        "Any dimension with valid=false has its score forced to 0.0 in the "
        "final ambiguity calculation. Be honest. Do not rubber-stamp."
    )


def draft_ambiguity_score(
    project_root: str,
    user_prompt_verbatim: str,
    goal_clarity: float,
    goal_evidence: str,
    constraint_clarity: float,
    constraint_evidence: str,
    success_criteria_clarity: float,
    success_evidence: str,
    blocking_questions: list[str],
    open_questions: list[str] | None = None,
) -> dict[str, Any]:
    """Stage Agent A's claimed scores and return an auditor prompt package.

    Step 1 of the audited two-step gate. Agent A submits per-dimension
    clarity scores with verbatim evidence quotes plus the user's original
    request text. MCP persists the claim to disk and returns an auditor
    prompt that must be dispatched to a sub-agent (CLI-native: Claude Code
    Task tool, pi -p, codex exec, etc.). The returned audit_token must
    appear in the sub-agent's verdict to be accepted by
    commit_ambiguity_audit.
    """
    _validate_score("goal_clarity", goal_clarity)
    _validate_score("constraint_clarity", constraint_clarity)
    _validate_score("success_criteria_clarity", success_criteria_clarity)
    _validate_evidence("goal_evidence", goal_evidence, goal_clarity)
    _validate_evidence("constraint_evidence", constraint_evidence, constraint_clarity)
    _validate_evidence("success_evidence", success_evidence, success_criteria_clarity)
    if not isinstance(blocking_questions, list):
        raise ValueError("blocking_questions must be a list of strings")
    open_qs = list(open_questions) if open_questions else []
    if not isinstance(user_prompt_verbatim, str) or len(user_prompt_verbatim.strip()) < MIN_USER_PROMPT_LEN:
        raise ValueError(
            f"user_prompt_verbatim must be the user's original request "
            f"(>= {MIN_USER_PROMPT_LEN} chars), not a summary"
        )

    draft_id = uuid.uuid4().hex[:12]
    audit_token = secrets.token_urlsafe(AUDIT_TOKEN_BYTES)

    claims = {
        "goal": {"score": float(goal_clarity), "evidence": goal_evidence.strip()},
        "constraint": {"score": float(constraint_clarity), "evidence": constraint_evidence.strip()},
        "success": {"score": float(success_criteria_clarity), "evidence": success_evidence.strip()},
    }

    draft = {
        "draft_id": draft_id,
        "audit_token": audit_token,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "user_prompt_verbatim": user_prompt_verbatim.strip(),
        "claims": claims,
        "blocking_questions": list(blocking_questions),
        "open_questions": open_qs,
    }

    drafts_dir = _drafts_dir(project_root)
    drafts_dir.mkdir(parents=True, exist_ok=True)
    _purge_old_drafts(drafts_dir)
    draft_path = drafts_dir / f"{draft_id}.json"
    draft_path.write_text(json.dumps(draft, indent=2, ensure_ascii=False), encoding="utf-8")

    auditor_prompt = _build_auditor_prompt(user_prompt_verbatim.strip(), claims, audit_token)

    append_gate_event(
        project_root,
        "draft_ambiguity_score",
        {
            "draft_id": draft_id,
            "claims_scores": {k: round(v["score"], 2) for k, v in claims.items()},
            "evidence_lengths": {k: len(v["evidence"]) for k, v in claims.items()},
            "blocking_count": len(blocking_questions),
        },
    )

    return {
        "draft_id": draft_id,
        "audit_token": audit_token,
        "auditor_prompt_markdown": auditor_prompt,
        "next_action": (
            "Dispatch a sub-agent with auditor_prompt_markdown using your CLI's "
            "native mechanism (Claude Code: Task tool; Pi: pi -p; Codex: codex exec). "
            "Pass the sub-agent's full transcript VERBATIM to commit_ambiguity_audit "
            f"with draft_id={draft_id!r}."
        ),
        "draft_path": str(draft_path),
    }


def _find_balanced_json_objects(text: str) -> list[str]:
    """Extract top-level balanced {...} blocks. Skips braces inside strings."""
    out: list[str] = []
    depth = 0
    start = -1
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start >= 0:
                out.append(text[start : i + 1])
                start = -1
    return out


def _parse_verdict(transcript: str, expected_token: str) -> dict[str, Any] | None:
    """Locate first JSON object whose audit_token matches. Returns None if none found."""
    for blob in _find_balanced_json_objects(transcript):
        try:
            obj = json.loads(blob)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get("audit_token") == expected_token:
            return obj
    return None


def _validate_verdict_schema(verdict: dict[str, Any]) -> tuple[bool, str]:
    dims = verdict.get("dimensions")
    if not isinstance(dims, dict):
        return False, "verdict missing 'dimensions' object"
    required = {"goal", "constraint", "success"}
    missing = required - dims.keys()
    if missing:
        return False, f"dimensions missing keys: {sorted(missing)}"
    for k in required:
        d = dims[k]
        if not isinstance(d, dict):
            return False, f"dimensions.{k} must be an object"
        if not isinstance(d.get("valid"), bool):
            return False, f"dimensions.{k}.valid must be a boolean"
        if not isinstance(d.get("reason"), str):
            return False, f"dimensions.{k}.reason must be a string"
    return True, ""


def _build_audited_report(
    claims: dict[str, dict[str, Any]],
    verdict: dict[str, Any],
    final_scores: dict[str, float],
    weighted: dict[str, float],
    total_clarity: float,
    ambiguity: float,
    blocking_questions: list[str],
    open_questions: list[str],
    proceed: bool,
) -> str:
    dims = verdict["dimensions"]
    lines = ["Audited Ambiguity Report"]
    for key, label, weight in [
        ("goal", "Goal", W_GOAL),
        ("constraint", "Constraint", W_CONSTRAINT),
        ("success", "Success criteria", W_SUCCESS),
    ]:
        orig = claims[key]["score"]
        final = final_scores[key]
        valid = dims[key]["valid"]
        reason = dims[key]["reason"]
        status = "VALID" if valid else "REJECTED"
        if valid:
            lines.append(
                f"- {label} clarity: {final:.2f} × {weight:.2f} = "
                f"{weighted[key]:.2f}  [{status}]"
            )
        else:
            lines.append(
                f"- {label} clarity: {orig:.2f} → {final:.2f} (forced) × {weight:.2f} = "
                f"{weighted[key]:.2f}  [{status}]"
            )
        lines.append(f"  evidence: {_truncate(claims[key]['evidence'])}")
        lines.append(f"  auditor: {_truncate(reason)}")
    lines.append(f"- Total clarity: {total_clarity:.2f}")
    lines.append(f"- Ambiguity (1 - clarity): {ambiguity:.2f}")
    lines.append(f"- Blocking questions: {len(blocking_questions)}")
    lines.append(f"- Open questions: {len(open_questions)}")
    lines.append(
        f"- Proceed: {'YES' if proceed else 'NO'} "
        f"(threshold {AMBIGUITY_THRESHOLD:.2f}, blocking must be 0)"
    )
    if blocking_questions:
        lines.append("")
        lines.append("Blocking questions:")
        for q in blocking_questions:
            lines.append(f"  - {q}")
    if open_questions:
        lines.append("")
        lines.append("Open questions:")
        for q in open_questions:
            lines.append(f"  - {q}")
    return "\n".join(lines)


def commit_ambiguity_audit(
    project_root: str,
    draft_id: str,
    auditor_transcript: str,
) -> dict[str, Any]:
    """Apply the sub-agent's verdict to a previously drafted ambiguity score.

    Step 2 of the audited two-step gate. Loads the draft created by
    draft_ambiguity_score, extracts the verdict JSON from auditor_transcript
    (must contain the matching audit_token), forces any dimension with
    valid=false to score 0.0, and returns the final proceed verdict.

    Errors that DO NOT consume the draft (Agent A may fix and retry):
      - draft_not_found / draft_corrupt
      - verdict_token_mismatch (no JSON object with matching token)
      - verdict_schema_invalid

    On successful parse, the draft is deleted (single-shot).
    """
    if not isinstance(draft_id, str) or not draft_id.strip():
        raise ValueError("draft_id must be a non-empty string")
    if not isinstance(auditor_transcript, str) or not auditor_transcript.strip():
        raise ValueError("auditor_transcript must be a non-empty string")

    drafts_dir = _drafts_dir(project_root)
    draft_path = drafts_dir / f"{draft_id.strip()}.json"
    if not draft_path.is_file():
        result = {
            "proceed": False,
            "error": "draft_not_found",
            "message": (
                f"No draft with id {draft_id!r}; expired (TTL {DRAFT_TTL_HOURS}h) "
                "or never created. Call draft_ambiguity_score first."
            ),
            "draft_id": draft_id,
        }
        append_gate_event(project_root, "commit_ambiguity_audit", {
            "draft_id": draft_id, "proceed": False, "error": "draft_not_found",
        })
        return result

    try:
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        result = {
            "proceed": False,
            "error": "draft_corrupt",
            "message": str(e),
            "draft_id": draft_id,
        }
        append_gate_event(project_root, "commit_ambiguity_audit", {
            "draft_id": draft_id, "proceed": False, "error": "draft_corrupt",
        })
        return result

    expected_token = draft["audit_token"]
    verdict = _parse_verdict(auditor_transcript, expected_token)
    if verdict is None:
        result = {
            "proceed": False,
            "error": "verdict_token_mismatch",
            "message": (
                "No JSON object with matching audit_token found in transcript. "
                "Either the sub-agent did not echo the token, the transcript was "
                "modified, or no sub-agent was actually dispatched."
            ),
            "draft_id": draft_id,
        }
        append_gate_event(project_root, "commit_ambiguity_audit", {
            "draft_id": draft_id, "proceed": False, "error": "verdict_token_mismatch",
        })
        return result

    schema_ok, schema_err = _validate_verdict_schema(verdict)
    if not schema_ok:
        result = {
            "proceed": False,
            "error": "verdict_schema_invalid",
            "message": schema_err,
            "draft_id": draft_id,
        }
        append_gate_event(project_root, "commit_ambiguity_audit", {
            "draft_id": draft_id, "proceed": False, "error": "verdict_schema_invalid",
            "schema_error": schema_err,
        })
        return result

    dims = verdict["dimensions"]
    claims = draft["claims"]
    final_scores: dict[str, float] = {}
    rejected: list[str] = []
    auditor_reasons: dict[str, str] = {}
    for key in ("goal", "constraint", "success"):
        original = float(claims[key]["score"])
        if not dims[key]["valid"]:
            final_scores[key] = 0.0
            rejected.append(key)
        else:
            final_scores[key] = original
        auditor_reasons[key] = dims[key]["reason"]

    weighted = {
        "goal": final_scores["goal"] * W_GOAL,
        "constraint": final_scores["constraint"] * W_CONSTRAINT,
        "success": final_scores["success"] * W_SUCCESS,
    }
    total_clarity = sum(weighted.values())
    ambiguity = 1.0 - total_clarity
    blocking = list(draft.get("blocking_questions", []))
    open_qs = list(draft.get("open_questions", []))
    proceed = ambiguity <= AMBIGUITY_THRESHOLD and len(blocking) == 0

    report = _build_audited_report(
        claims=claims,
        verdict=verdict,
        final_scores=final_scores,
        weighted=weighted,
        total_clarity=total_clarity,
        ambiguity=ambiguity,
        blocking_questions=blocking,
        open_questions=open_qs,
        proceed=proceed,
    )

    result = {
        "draft_id": draft_id,
        "proceed": proceed,
        "ambiguity": ambiguity,
        "total_clarity": round(total_clarity, 4),
        "final_scores": {k: round(v, 2) for k, v in final_scores.items()},
        "weighted": {k: round(v, 2) for k, v in weighted.items()},
        "rejected_dimensions": rejected,
        "auditor_reasons": auditor_reasons,
        "blocking_count": len(blocking),
        "open_question_count": len(open_qs),
        "report_markdown": report,
    }

    append_gate_event(
        project_root,
        "commit_ambiguity_audit",
        {
            "draft_id": draft_id,
            "proceed": proceed,
            "ambiguity": round(ambiguity, 4),
            "rejected_dimensions": rejected,
            "blocking_count": len(blocking),
        },
    )

    try:
        draft_path.unlink()
    except OSError:
        pass

    return result

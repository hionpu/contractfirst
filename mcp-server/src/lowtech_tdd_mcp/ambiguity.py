"""score_ambiguity: clarity-score computation with required evidence text.

Each per-dimension clarity score must be accompanied by a verbatim quote
from the user's request (or an explicit "none" if the user said nothing
about the dimension — which forces the score low). The evidence quote is
included in the rendered report so a human reviewer can judge whether
the quote actually justifies the score. The deterministic arithmetic
prevents the AI from quietly inflating ambiguity; the required quote
prevents the AI from quietly inflating clarity.
"""

from __future__ import annotations

from typing import Any

from .gatelog import append_gate_event

W_GOAL = 0.40
W_CONSTRAINT = 0.30
W_SUCCESS = 0.30
AMBIGUITY_THRESHOLD = 0.20
MIN_EVIDENCE_LEN = 8
NONE_TOKEN = "none"


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

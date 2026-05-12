"""score_ambiguity: deterministic clarity-score computation."""

from __future__ import annotations

from typing import Any

W_GOAL = 0.40
W_CONSTRAINT = 0.30
W_SUCCESS = 0.30
AMBIGUITY_THRESHOLD = 0.20


def _validate_score(name: str, value: float) -> None:
    if not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number, got {type(value).__name__}")
    if value < 0.0 or value > 1.0:
        raise ValueError(f"{name} must be in [0.0, 1.0], got {value}")


def _build_report(
    goal: float,
    constraint: float,
    success: float,
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
        f"- Constraint clarity: {constraint:.2f} × {W_CONSTRAINT:.2f} = {w_constraint:.2f}",
        f"- Success criteria clarity: {success:.2f} × {W_SUCCESS:.2f} = {w_success:.2f}",
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
    constraint_clarity: float,
    success_criteria_clarity: float,
    blocking_questions: list[str],
    open_questions: list[str] | None = None,
) -> dict[str, Any]:
    _validate_score("goal_clarity", goal_clarity)
    _validate_score("constraint_clarity", constraint_clarity)
    _validate_score("success_criteria_clarity", success_criteria_clarity)
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

    return {
        "scores": {
            "goal_clarity": round(goal_clarity, 2),
            "constraint_clarity": round(constraint_clarity, 2),
            "success_criteria_clarity": round(success_criteria_clarity, 2),
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

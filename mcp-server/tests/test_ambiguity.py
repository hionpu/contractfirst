import pytest

from lowtech_tdd_mcp.ambiguity import score_ambiguity


# A reusable evidence block that always satisfies the >=8 char requirement.
GOAL_EV = "user said: 'show top 10 players by score'"
CON_EV = "user said: 'must not modify existing leaderboard'"
SUC_EV = "user said: 'verify by API returning sorted array'"


def test_happy_path_proceed():
    result = score_ambiguity(
        goal_clarity=0.9,
        goal_evidence=GOAL_EV,
        constraint_clarity=0.9,
        constraint_evidence=CON_EV,
        success_criteria_clarity=0.9,
        success_evidence=SUC_EV,
        blocking_questions=[],
        open_questions=["nice-to-have: caching?"],
    )
    assert result["proceed"] is True
    assert result["ambiguity"] == pytest.approx(0.10, rel=1e-9)
    assert result["blocking_count"] == 0
    assert result["open_question_count"] == 1
    assert result["scores"]["goal_clarity"] == 0.9
    assert result["weighted"]["goal"] == 0.36
    assert "Ambiguity Report" in result["report_markdown"]
    assert "evidence:" in result["report_markdown"]
    assert result["evidence"]["goal"] == GOAL_EV


def test_blocking_questions_force_stop():
    result = score_ambiguity(
        goal_clarity=1.0,
        goal_evidence=GOAL_EV,
        constraint_clarity=1.0,
        constraint_evidence=CON_EV,
        success_criteria_clarity=1.0,
        success_evidence=SUC_EV,
        blocking_questions=["What is the rate limit?"],
    )
    assert result["ambiguity"] == pytest.approx(0.0, abs=1e-9)
    assert result["proceed"] is False
    assert "Proceed: NO" in result["report_markdown"]


def test_invalid_score_raises():
    with pytest.raises(ValueError) as exc:
        score_ambiguity(
            goal_clarity=1.5,
            goal_evidence=GOAL_EV,
            constraint_clarity=0.5,
            constraint_evidence=CON_EV,
            success_criteria_clarity=0.5,
            success_evidence=SUC_EV,
            blocking_questions=[],
        )
    assert "goal_clarity" in str(exc.value)


def test_ambiguity_above_threshold_blocks_proceed():
    result = score_ambiguity(
        goal_clarity=0.5,
        goal_evidence=GOAL_EV,
        constraint_clarity=0.5,
        constraint_evidence=CON_EV,
        success_criteria_clarity=0.5,
        success_evidence=SUC_EV,
        blocking_questions=[],
    )
    assert result["ambiguity"] == pytest.approx(0.5, rel=1e-9)
    assert result["proceed"] is False


def test_empty_evidence_rejected():
    with pytest.raises(ValueError) as exc:
        score_ambiguity(
            goal_clarity=0.9,
            goal_evidence="   ",
            constraint_clarity=0.9,
            constraint_evidence=CON_EV,
            success_criteria_clarity=0.9,
            success_evidence=SUC_EV,
            blocking_questions=[],
        )
    assert "goal_evidence" in str(exc.value)


def test_short_evidence_rejected():
    with pytest.raises(ValueError) as exc:
        score_ambiguity(
            goal_clarity=0.9,
            goal_evidence="abc",
            constraint_clarity=0.9,
            constraint_evidence=CON_EV,
            success_criteria_clarity=0.9,
            success_evidence=SUC_EV,
            blocking_questions=[],
        )
    assert "8 characters" in str(exc.value)


def test_none_evidence_forces_low_score():
    """'none' is allowed but forbids high clarity — closes the bypass loophole."""
    with pytest.raises(ValueError) as exc:
        score_ambiguity(
            goal_clarity=0.9,
            goal_evidence="none",
            constraint_clarity=0.9,
            constraint_evidence=CON_EV,
            success_criteria_clarity=0.9,
            success_evidence=SUC_EV,
            blocking_questions=[],
        )
    assert "'none'" in str(exc.value) or "none" in str(exc.value)


def test_none_evidence_low_score_ok():
    """When the user said nothing about a dimension, score must be <= 0.30 and that's fine."""
    result = score_ambiguity(
        goal_clarity=0.9,
        goal_evidence=GOAL_EV,
        constraint_clarity=0.2,
        constraint_evidence="none",
        success_criteria_clarity=0.9,
        success_evidence=SUC_EV,
        blocking_questions=[],
    )
    assert result["evidence"]["constraint"] == "none"
    # 0.9*0.4 + 0.2*0.3 + 0.9*0.3 = 0.36 + 0.06 + 0.27 = 0.69 → ambiguity 0.31
    assert result["proceed"] is False


def test_gates_jsonl_written_when_project_root_given(tmp_path):
    score_ambiguity(
        goal_clarity=0.9,
        goal_evidence=GOAL_EV,
        constraint_clarity=0.9,
        constraint_evidence=CON_EV,
        success_criteria_clarity=0.9,
        success_evidence=SUC_EV,
        blocking_questions=[],
        project_root=str(tmp_path),
    )
    gates = tmp_path / ".lowtech-tdd" / "gates.jsonl"
    assert gates.is_file()
    content = gates.read_text(encoding="utf-8")
    assert "score_ambiguity" in content
    assert '"proceed": true' in content

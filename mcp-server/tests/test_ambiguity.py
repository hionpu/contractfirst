import pytest

from lowtech_tdd_mcp.ambiguity import score_ambiguity


def test_happy_path_proceed():
    result = score_ambiguity(
        goal_clarity=0.9,
        constraint_clarity=0.9,
        success_criteria_clarity=0.9,
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


def test_blocking_questions_force_stop():
    result = score_ambiguity(
        goal_clarity=1.0,
        constraint_clarity=1.0,
        success_criteria_clarity=1.0,
        blocking_questions=["What is the rate limit?"],
    )
    assert result["ambiguity"] == pytest.approx(0.0, abs=1e-9)
    assert result["proceed"] is False
    assert "Proceed: NO" in result["report_markdown"]


def test_invalid_score_raises():
    with pytest.raises(ValueError) as exc:
        score_ambiguity(
            goal_clarity=1.5,
            constraint_clarity=0.5,
            success_criteria_clarity=0.5,
            blocking_questions=[],
        )
    assert "goal_clarity" in str(exc.value)


def test_ambiguity_above_threshold_blocks_proceed():
    result = score_ambiguity(
        goal_clarity=0.5,
        constraint_clarity=0.5,
        success_criteria_clarity=0.5,
        blocking_questions=[],
    )
    assert result["ambiguity"] == pytest.approx(0.5, rel=1e-9)
    assert result["proceed"] is False

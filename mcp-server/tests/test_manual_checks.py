import json
from pathlib import Path

import pytest

from lowtech_tdd_mcp.manual_checks import read_summary, track_manual_checks


def test_declare_creates_ledger(tmp_path: Path):
    result = track_manual_checks(
        project_root=str(tmp_path),
        feature="minigame-ui",
        op="declare",
        checks=[
            {"id": "V1", "description": "UI 3x trigger → one window"},
            {"id": "V2", "description": "close + reopen works"},
            {"id": "V3", "description": "optional perf check", "required": False},
        ],
    )
    assert result["summary"]["total"] == 3
    assert result["summary"]["required"] == 2
    assert result["summary"]["optional"] == 1
    assert result["summary"]["all_required_resolved"] is False
    assert set(result["summary"]["pending_ids"]) == {"V1", "V2"}

    ledger = tmp_path / ".lowtech-tdd" / "manual-checks" / "minigame-ui.json"
    assert ledger.is_file()
    data = json.loads(ledger.read_text(encoding="utf-8"))
    assert data["feature"] == "minigame-ui"
    assert len(data["checks"]) == 3


def test_confirm_resolves_pending(tmp_path: Path):
    track_manual_checks(
        project_root=str(tmp_path),
        feature="checkout",
        op="declare",
        checks=[{"id": "V1", "description": "manual playtest"}],
    )
    result = track_manual_checks(
        project_root=str(tmp_path),
        feature="checkout",
        op="confirm",
        check_id="V1",
        note="playtest 3 min @ 1080p",
    )
    assert result["summary"]["all_required_resolved"] is True
    assert result["summary"]["pending_ids"] == []
    assert result["checks"][0]["status"] == "confirmed"
    assert result["checks"][0]["note"] == "playtest 3 min @ 1080p"


def test_handoff_counts_as_resolved(tmp_path: Path):
    track_manual_checks(
        project_root=str(tmp_path),
        feature="x",
        op="declare",
        checks=[{"id": "V1", "description": "QA team will run"}],
    )
    result = track_manual_checks(
        project_root=str(tmp_path),
        feature="x",
        op="handoff",
        check_id="V1",
        note="QA ticket #1234",
    )
    assert result["summary"]["all_required_resolved"] is True
    assert result["summary"]["handed_off"] == 1


def test_declare_replace_resets(tmp_path: Path):
    track_manual_checks(
        project_root=str(tmp_path),
        feature="x",
        op="declare",
        checks=[{"id": "V1", "description": "first"}],
    )
    track_manual_checks(
        project_root=str(tmp_path),
        feature="x",
        op="declare",
        checks=[{"id": "V2", "description": "second"}],
        replace=True,
    )
    summary = read_summary(str(tmp_path), "x")
    assert summary["total"] == 1
    assert summary["pending_ids"] == ["V2"]


def test_declare_append_preserves_existing(tmp_path: Path):
    track_manual_checks(
        project_root=str(tmp_path),
        feature="x",
        op="declare",
        checks=[{"id": "V1", "description": "first"}],
    )
    track_manual_checks(
        project_root=str(tmp_path),
        feature="x",
        op="declare",
        checks=[{"id": "V2", "description": "second"}],
    )
    summary = read_summary(str(tmp_path), "x")
    assert summary["total"] == 2


def test_duplicate_id_rejected(tmp_path: Path):
    track_manual_checks(
        project_root=str(tmp_path),
        feature="x",
        op="declare",
        checks=[{"id": "V1", "description": "first"}],
    )
    with pytest.raises(ValueError) as exc:
        track_manual_checks(
            project_root=str(tmp_path),
            feature="x",
            op="declare",
            checks=[{"id": "V1", "description": "dup"}],
        )
    assert "duplicate" in str(exc.value).lower()


def test_invalid_feature_slug_rejected(tmp_path: Path):
    with pytest.raises(ValueError):
        track_manual_checks(
            project_root=str(tmp_path),
            feature="../etc/passwd",
            op="declare",
            checks=[{"id": "V1", "description": "x"}],
        )


def test_confirm_requires_check_id(tmp_path: Path):
    with pytest.raises(ValueError):
        track_manual_checks(project_root=str(tmp_path), feature="x", op="confirm")


def test_confirm_unknown_check_raises(tmp_path: Path):
    track_manual_checks(
        project_root=str(tmp_path),
        feature="x",
        op="declare",
        checks=[{"id": "V1", "description": "x"}],
    )
    with pytest.raises(ValueError) as exc:
        track_manual_checks(
            project_root=str(tmp_path),
            feature="x",
            op="confirm",
            check_id="V999",
        )
    assert "V999" in str(exc.value)


def test_summary_for_unknown_feature_is_empty(tmp_path: Path):
    result = track_manual_checks(
        project_root=str(tmp_path), feature="never-declared", op="summary"
    )
    assert result["summary"]["total"] == 0
    assert result["summary"]["all_required_resolved"] is True  # vacuously


def test_gates_log_appended(tmp_path: Path):
    track_manual_checks(
        project_root=str(tmp_path),
        feature="x",
        op="declare",
        checks=[{"id": "V1", "description": "x"}],
    )
    track_manual_checks(
        project_root=str(tmp_path), feature="x", op="confirm", check_id="V1"
    )
    gates = tmp_path / ".lowtech-tdd" / "gates.jsonl"
    assert gates.is_file()
    lines = gates.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 2
    assert all("track_manual_checks" in ln for ln in lines)

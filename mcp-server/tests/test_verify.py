import os
import stat
import sys
from pathlib import Path

import pytest

from lowtech_tdd_mcp.manual_checks import track_manual_checks
from lowtech_tdd_mcp.verify import run_verify


def _write_verify_script(root: Path, exit_code: int = 0, message: str = "ok") -> str:
    """Write a tiny cross-platform verify script. Returns the relative path."""
    if sys.platform.startswith("win"):
        rel = "verify.cmd"
        body = f"@echo off\r\necho {message}\r\nexit /b {exit_code}\r\n"
        (root / rel).write_text(body, encoding="utf-8")
    else:
        rel = "verify.sh"
        script = root / rel
        script.write_text(f"#!/usr/bin/env bash\necho {message}\nexit {exit_code}\n")
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return rel


def test_happy_path_with_verify_script(tmp_path: Path):
    rel = _write_verify_script(tmp_path, exit_code=0, message="all-good")
    result = run_verify(project_root=str(tmp_path), scope="full", verify_script=rel)
    assert result["overall"] == "pass"
    assert result["automatic_overall"] == "pass"
    assert result["scope_executed"] == "full"
    assert result["failed_step_names"] == []
    assert len(result["steps"]) == 1
    assert result["steps"][0]["status"] == "pass"
    assert "all-good" in result["steps"][0]["stdout_tail"]
    log_path = Path(result["log_path"])
    assert log_path.is_file()
    assert ".lowtech-tdd" in str(log_path)


def test_failing_verify_script(tmp_path: Path):
    rel = _write_verify_script(tmp_path, exit_code=2, message="boom")
    result = run_verify(project_root=str(tmp_path), scope="test", verify_script=rel)
    assert result["overall"] == "fail"
    assert result["failed_step_names"]
    assert result["steps"][0]["exit_code"] == 2


def test_invalid_scope_raises():
    with pytest.raises(ValueError):
        run_verify(project_root=os.getcwd(), scope="bogus")


def test_unknown_project_returns_not_configured(tmp_path: Path):
    result = run_verify(project_root=str(tmp_path), scope="full")
    assert result["overall"] in ("partial", "fail")
    assert all(s["status"] == "not_configured" for s in result["steps"])


def test_manual_gate_downgrades_pass_to_pending(tmp_path: Path):
    """A green automatic run + pending manual check → overall=pending_manual."""
    rel = _write_verify_script(tmp_path, exit_code=0, message="ok")
    track_manual_checks(
        project_root=str(tmp_path),
        feature="minigame-ui",
        op="declare",
        checks=[{"id": "V1", "description": "manual playtest"}],
    )
    result = run_verify(
        project_root=str(tmp_path),
        scope="full",
        verify_script=rel,
        feature="minigame-ui",
    )
    assert result["automatic_overall"] == "pass"
    assert result["overall"] == "pending_manual"
    assert "V1" in (result["manual_checks"] or {}).get("pending_ids", [])
    assert "manual checks pending" in result["summary"]


def test_manual_gate_clears_after_confirm(tmp_path: Path):
    rel = _write_verify_script(tmp_path, exit_code=0, message="ok")
    track_manual_checks(
        project_root=str(tmp_path),
        feature="x",
        op="declare",
        checks=[{"id": "V1", "description": "play check"}],
    )
    track_manual_checks(
        project_root=str(tmp_path), feature="x", op="confirm", check_id="V1"
    )
    result = run_verify(
        project_root=str(tmp_path),
        scope="full",
        verify_script=rel,
        feature="x",
    )
    assert result["overall"] == "pass"
    assert result["manual_checks"]["all_required_resolved"] is True


def test_manual_gate_does_not_mask_real_failure(tmp_path: Path):
    """If automatic fails, overall stays 'fail' regardless of manual ledger."""
    rel = _write_verify_script(tmp_path, exit_code=3, message="boom")
    track_manual_checks(
        project_root=str(tmp_path),
        feature="x",
        op="declare",
        checks=[{"id": "V1", "description": "play check"}],
    )
    result = run_verify(
        project_root=str(tmp_path),
        scope="full",
        verify_script=rel,
        feature="x",
    )
    assert result["overall"] == "fail"
    assert result["automatic_overall"] == "fail"


def test_run_verify_logs_to_gates_jsonl(tmp_path: Path):
    rel = _write_verify_script(tmp_path, exit_code=0, message="ok")
    run_verify(project_root=str(tmp_path), scope="full", verify_script=rel)
    gates = tmp_path / ".lowtech-tdd" / "gates.jsonl"
    assert gates.is_file()
    assert "run_verify" in gates.read_text(encoding="utf-8")


def test_no_feature_skips_manual_check_consultation(tmp_path: Path):
    rel = _write_verify_script(tmp_path, exit_code=0, message="ok")
    track_manual_checks(
        project_root=str(tmp_path),
        feature="x",
        op="declare",
        checks=[{"id": "V1", "description": "play check"}],
    )
    result = run_verify(project_root=str(tmp_path), scope="full", verify_script=rel)
    assert result["overall"] == "pass"  # no feature given → ledger ignored
    assert result["manual_checks"] is None

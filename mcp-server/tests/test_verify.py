import os
import stat
import sys
from pathlib import Path

import pytest

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

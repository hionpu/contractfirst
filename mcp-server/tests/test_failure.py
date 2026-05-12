from pathlib import Path

from lowtech_tdd_mcp.failure import analyze_verify_failure


def _write_log(root: Path, body: str) -> Path:
    log_dir = root / ".lowtech-tdd"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / "verify-20260511-000000.log"
    log.write_text(body, encoding="utf-8")
    return log


def test_contract_sensitive_test_failure_blocks_patch(tmp_path: Path):
    log = _write_log(
        tmp_path,
        """## step: test
status: fail
--- stdout ---
============================= FAILURES =============================
_____________________________ test_cart_total ______________________
tests/test_cart.py:42: in test_cart_total
    assert cart.total() == 150
E   AssertionError: expected 150, got 165
src/billing/cart.py:18: in total
    return sum(self._apply_tax(line) for line in self.lines)
INV-3 violated
""",
    )
    (tmp_path / "src" / "billing").mkdir(parents=True)
    (tmp_path / "src" / "billing" / "cart.py").write_text("# cart\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_cart.py").write_text("# test\n")

    result = analyze_verify_failure(
        project_root=str(tmp_path),
        verify_log_path=str(log),
        failed_step="test",
    )
    assert result["category"] == "contract_sensitive"
    assert result["h4_gate"]["patch_allowed"] is False
    assert "AssertionError" in result["error_summary"]
    assert any("cart" in f for f in result["suspected_files"])
    assert result["hypotheses"]
    assert result["hypotheses"][0]["violated_invariant"] == "INV-3"
    # No fix snippets must appear in any string field for contract_sensitive.
    flat = repr(result)
    assert "```" not in flat


def test_routine_lint_failure_allows_patch(tmp_path: Path):
    log = _write_log(
        tmp_path,
        """## step: lint
status: fail
--- stdout ---
src/utils.py:10:1: F401 'os' imported but unused
""",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "utils.py").write_text("import os\n")
    result = analyze_verify_failure(
        project_root=str(tmp_path),
        verify_log_path=str(log),
        failed_step="lint",
    )
    assert result["category"] == "routine"
    assert result["h4_gate"]["patch_allowed"] is True
    assert result["fix_strategy_options"]


def test_missing_log_returns_empty_hypotheses(tmp_path: Path):
    result = analyze_verify_failure(
        project_root=str(tmp_path),
        verify_log_path=str(tmp_path / "does-not-exist.log"),
        failed_step="test",
    )
    assert result["hypotheses"] == []
    assert "no error lines" in result["error_summary"]
    # An empty log still defaults to contract_sensitive for "test" step.
    assert result["category"] == "contract_sensitive"
    assert result["h4_gate"]["patch_allowed"] is False

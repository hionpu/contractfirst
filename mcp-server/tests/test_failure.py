from pathlib import Path

from contractfirst.failure import analyze_verify_failure


def _write_log(root: Path, body: str) -> Path:
    log_dir = root / ".contractfirst"
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
    assert result["classification_signals"]  # must report why
    # No fix snippets must appear in any string field for contract_sensitive.
    flat = repr(result)
    assert "```" not in flat


def test_jest_failure_classified_contract_sensitive(tmp_path: Path):
    """Jest output uses '●' headers — must trip the structured detector even on a typecheck step."""
    log_dir = tmp_path / ".contractfirst"
    log_dir.mkdir(parents=True)
    log = log_dir / "verify.log"
    log.write_text(
        "## step: typecheck\nstatus: fail\n--- stdout ---\n"
        " FAIL src/cart.test.ts\n"
        "  ● Cart › computes total with tax\n"
        "    expect(received).toBe(expected)\n"
        "    Expected: 150\n"
        "    Received: 165\n",
        encoding="utf-8",
    )
    result = analyze_verify_failure(
        project_root=str(tmp_path),
        verify_log_path=str(log),
        failed_step="typecheck",
    )
    assert result["category"] == "contract_sensitive"
    assert any("structured:" in s for s in result["classification_signals"])


def test_go_failure_classified_contract_sensitive(tmp_path: Path):
    log_dir = tmp_path / ".contractfirst"
    log_dir.mkdir(parents=True)
    log = log_dir / "verify.log"
    log.write_text(
        "## step: build\nstatus: fail\n--- stdout ---\n"
        "--- FAIL: TestCart_Total (0.00s)\n"
        "    cart_test.go:42: got 165, want 150\n",
        encoding="utf-8",
    )
    result = analyze_verify_failure(
        project_root=str(tmp_path),
        verify_log_path=str(log),
        failed_step="build",
    )
    assert result["category"] == "contract_sensitive"


def test_lint_with_no_contract_signal_stays_routine(tmp_path: Path):
    """The keyword 'should' alone (no structured marker, non-contract path) must NOT flip to contract."""
    log_dir = tmp_path / ".contractfirst"
    log_dir.mkdir(parents=True)
    log = log_dir / "verify.log"
    log.write_text(
        "## step: lint\nstatus: fail\n--- stdout ---\n"
        "src/utils.py:10:1: E501 line too long; line should be wrapped\n",
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "utils.py").write_text("# x\n")
    result = analyze_verify_failure(
        project_root=str(tmp_path),
        verify_log_path=str(log),
        failed_step="lint",
    )
    assert result["category"] == "routine"


def test_contract_path_flips_classification(tmp_path: Path):
    """A failure pointing at a tests/ file flips classification even with no exception."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("# t\n")
    log_dir = tmp_path / ".contractfirst"
    log_dir.mkdir(parents=True)
    log = log_dir / "verify.log"
    log.write_text(
        "## step: build\nstatus: fail\n--- stdout ---\n"
        "tests/test_x.py:10 build error\n",
        encoding="utf-8",
    )
    result = analyze_verify_failure(
        project_root=str(tmp_path),
        verify_log_path=str(log),
        failed_step="build",
    )
    assert result["category"] == "contract_sensitive"
    assert any("path:" in s for s in result["classification_signals"])


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

from pathlib import Path

from lowtech_tdd_mcp.links import verify_links


def _scaffold(root: Path) -> None:
    (root / "docs" / "specs").mkdir(parents=True)
    (root / "docs" / "invariants").mkdir(parents=True)


def test_complete_cross_reference(tmp_path: Path):
    _scaffold(tmp_path)
    spec = tmp_path / "docs" / "specs" / "checkout.md"
    inv = tmp_path / "docs" / "invariants" / "payment.md"
    spec.write_text(
        "# Checkout\n\n## Links\n- [payment invariant](../invariants/payment.md)\n"
    )
    inv.write_text(
        "# Payment Invariants\n\nReciprocal: [checkout spec](../specs/checkout.md)\n"
    )
    result = verify_links(project_root=str(tmp_path), feature="checkout")
    assert result["status"] == "complete"
    assert result["missing"] == []
    assert result["stale"] == []
    assert result["checked_files"] == 1


def test_missing_target_reported(tmp_path: Path):
    _scaffold(tmp_path)
    spec = tmp_path / "docs" / "specs" / "checkout.md"
    spec.write_text(
        "# Checkout\n\n## Links\n- [ghost](../invariants/ghost.md)\n"
    )
    result = verify_links(project_root=str(tmp_path), feature="checkout")
    assert result["status"] == "incomplete"
    assert len(result["missing"]) == 1
    assert result["missing"][0]["to"].endswith("ghost.md")


def test_stale_back_link_reported(tmp_path: Path):
    _scaffold(tmp_path)
    spec = tmp_path / "docs" / "specs" / "checkout.md"
    inv = tmp_path / "docs" / "invariants" / "payment.md"
    spec.write_text(
        "## Links\n- [payment](../invariants/payment.md)\n"
    )
    inv.write_text("# Payment Invariants\n\nNo back link here.\n")
    result = verify_links(project_root=str(tmp_path), feature="checkout")
    assert result["status"] == "incomplete"
    assert any(s["to"].endswith("payment.md") for s in result["stale"])


def test_not_configured_when_no_specs_dir(tmp_path: Path):
    result = verify_links(project_root=str(tmp_path))
    assert result["status"] == "not_configured"
    assert result["checked_files"] == 0


# ── Fix 1: <!-- Links --> bare-block parser tests ─────────────────────────────


def test_bare_links_block_complete(tmp_path: Path):
    """Happy path: spec with <!-- Links --> block, referenced files exist with back-links."""
    _scaffold(tmp_path)
    spec = tmp_path / "docs" / "specs" / "minigame-ui.md"
    inv = tmp_path / "docs" / "invariants" / "session-rules.md"
    spec.write_text(
        "<!-- Links -->\n"
        "- Specs: (this file)\n"
        "- Invariants: [session-rules.md](../invariants/session-rules.md)\n"
        "\n"
        "# Spec: MiniGame UI\n"
    )
    inv.write_text(
        "<!-- Links -->\n"
        "- Specs: [minigame-ui.md](../specs/minigame-ui.md)\n"
        "- Invariants: (this file)\n"
        "\n"
        "# Session Rules\n"
    )
    result = verify_links(project_root=str(tmp_path), feature="minigame-ui")
    assert result["status"] == "complete", result
    assert result["missing"] == []
    assert result["stale"] == []
    assert result["checked_files"] == 1


def test_bare_links_block_missing_target(tmp_path: Path):
    """Spec references a file that doesn't exist."""
    _scaffold(tmp_path)
    spec = tmp_path / "docs" / "specs" / "checkout.md"
    spec.write_text(
        "<!-- Links -->\n"
        "- Specs: (this file)\n"
        "- Invariants: [ghost.md](../invariants/ghost.md)\n"
    )
    result = verify_links(project_root=str(tmp_path), feature="checkout")
    assert result["status"] == "incomplete"
    assert len(result["missing"]) == 1
    assert result["missing"][0]["to"].endswith("ghost.md")


def test_bare_links_block_stale_back_link(tmp_path: Path):
    """Referenced file exists but has no back-link to the spec."""
    _scaffold(tmp_path)
    spec = tmp_path / "docs" / "specs" / "checkout.md"
    inv = tmp_path / "docs" / "invariants" / "payment.md"
    spec.write_text(
        "<!-- Links -->\n"
        "- Specs: (this file)\n"
        "- Invariants: [payment.md](../invariants/payment.md)\n"
    )
    inv.write_text("# Payment\n\nNo back link here.\n")
    result = verify_links(project_root=str(tmp_path), feature="checkout")
    assert result["status"] == "incomplete"
    assert any(s["to"].endswith("payment.md") for s in result["stale"])


def test_bare_links_self_reference_skipped(tmp_path: Path):
    """(this file) entries must not be treated as link targets to validate."""
    _scaffold(tmp_path)
    spec = tmp_path / "docs" / "specs" / "solo.md"
    spec.write_text(
        "<!-- Links -->\n"
        "- Specs: (this file)\n"
        "- Invariants: (this file)\n"
        "- Tests: (this file)\n"
    )
    result = verify_links(project_root=str(tmp_path), feature="solo")
    # Only "this file" entries → no targets to validate → no missing/stale
    assert result["missing"] == []
    assert result["stale"] == []


def test_config_json_overrides_default_link_dirs(tmp_path: Path):
    """`.lowtech-tdd/config.json` link_dirs override the built-in defaults."""
    (tmp_path / "design").mkdir()
    (tmp_path / "design" / "specs").mkdir()
    (tmp_path / "design" / "invariants").mkdir()
    (tmp_path / ".lowtech-tdd").mkdir()
    (tmp_path / ".lowtech-tdd" / "config.json").write_text(
        '{"link_dirs": {"specs": "design/specs", "invariants": "design/invariants"}}',
        encoding="utf-8",
    )
    spec = tmp_path / "design" / "specs" / "checkout.md"
    inv = tmp_path / "design" / "invariants" / "payment.md"
    spec.write_text(
        "## Links\n- [payment](../invariants/payment.md)\n", encoding="utf-8"
    )
    inv.write_text(
        "# Payment\n[back](../specs/checkout.md)\n", encoding="utf-8"
    )
    result = verify_links(project_root=str(tmp_path), feature="checkout")
    assert result["status"] == "complete"
    assert result["checked_files"] == 1


def test_per_call_link_dirs_outrank_config(tmp_path: Path):
    """An explicit link_dirs arg overrides config.json."""
    (tmp_path / ".lowtech-tdd").mkdir()
    (tmp_path / ".lowtech-tdd" / "config.json").write_text(
        '{"link_dirs": {"specs": "wrong-path"}}', encoding="utf-8"
    )
    (tmp_path / "docs" / "specs").mkdir(parents=True)
    spec = tmp_path / "docs" / "specs" / "x.md"
    spec.write_text("# x\n", encoding="utf-8")
    result = verify_links(
        project_root=str(tmp_path),
        feature="x",
        link_dirs={"specs": "docs/specs"},
    )
    # spec exists at docs/specs/x.md and was found → not "not_configured"
    assert result["status"] != "not_configured"


def test_bare_links_multiple_targets_per_line(tmp_path: Path):
    """A single category line can list multiple comma-separated markdown links."""
    _scaffold(tmp_path)
    spec_a = tmp_path / "docs" / "specs" / "alpha.md"
    spec_b = tmp_path / "docs" / "specs" / "beta.md"
    inv = tmp_path / "docs" / "invariants" / "shared.md"
    inv.write_text(
        "<!-- Links -->\n"
        "- Specs: [alpha.md](../specs/alpha.md), [beta.md](../specs/beta.md)\n"
        "- Invariants: (this file)\n"
    )
    spec_a.write_text(
        "<!-- Links -->\n"
        "- Specs: (this file)\n"
        "- Invariants: [shared.md](../invariants/shared.md)\n"
    )
    spec_b.write_text(
        "<!-- Links -->\n"
        "- Specs: (this file)\n"
        "- Invariants: [shared.md](../invariants/shared.md)\n"
    )
    # Run with no feature filter so both specs are checked
    result = verify_links(project_root=str(tmp_path))
    # alpha and beta both link to shared; shared back-links to both → no stale/missing
    assert result["missing"] == [], result
    assert result["stale"] == [], result

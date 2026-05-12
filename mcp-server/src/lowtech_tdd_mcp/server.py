"""FastMCP server for the four lowtech-tdd checkpoint tools."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .ambiguity import score_ambiguity as _score_ambiguity
from .failure import analyze_verify_failure as _analyze_verify_failure
from .links import verify_links as _verify_links
from .verify import run_verify as _run_verify

mcp = FastMCP("lowtech-tdd-mcp")


@mcp.tool()
def run_verify(
    project_root: str,
    scope: str = "full",
    verify_script: str = "./verify.sh",
) -> dict[str, Any]:
    """Execute the project's verification suite and return structured results.

    Use this instead of trusting an AI's claim that tests passed. The tool either
    runs the project's verify.sh (passing `scope` as its first argument) or falls
    back to language-detected defaults (npm or pytest/mypy/ruff). Per-step exit
    codes, durations, and truncated logs are returned; full logs are saved under
    .lowtech-tdd/.
    """
    return _run_verify(project_root=project_root, scope=scope, verify_script=verify_script)


@mcp.tool()
def score_ambiguity(
    goal_clarity: float,
    constraint_clarity: float,
    success_criteria_clarity: float,
    blocking_questions: list[str],
    open_questions: list[str] | None = None,
) -> dict[str, Any]:
    """Compute the deterministic ambiguity score from the caller's clarity scores.

    The AI must provide three per-dimension clarity scores (0.0-1.0); the tool
    weights them (0.40 / 0.30 / 0.30) and decides whether to proceed. A spec is
    proceed-able only when ambiguity <= 0.20 AND no blocking questions remain.
    The returned report_markdown is the verbatim template the lowtech-tdd skill
    expects to print.
    """
    return _score_ambiguity(
        goal_clarity=goal_clarity,
        constraint_clarity=constraint_clarity,
        success_criteria_clarity=success_criteria_clarity,
        blocking_questions=blocking_questions,
        open_questions=open_questions,
    )


@mcp.tool()
def verify_links(
    project_root: str,
    feature: str | None = None,
    link_dirs: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Check that contract artifacts cross-reference each other correctly.

    Parses each spec's `## Links` section (or `<!-- LINKS -->` block), resolves
    targets on disk, and verifies a reciprocal back-link exists. Reports three
    categories: missing (target file not found), stale (target exists but no
    back-link), orphaned (invariant/interface/test file not referenced by any
    spec — full-scan only). Read-only; never edits files.
    """
    return _verify_links(project_root=project_root, feature=feature, link_dirs=link_dirs)


@mcp.tool()
def analyze_verify_failure(
    project_root: str,
    verify_log_path: str,
    failed_step: str,
    recent_diff: str | None = None,
    contract_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Produce structured root-cause hypotheses for a verification failure.

    Reads the saved verify log, classifies the failure as contract_sensitive or
    routine, and returns hypotheses with evidence. For contract_sensitive
    failures the H4 gate forbids a patch (patch_allowed=False) — the human must
    approve a fix strategy first. For routine failures (lint, simple typos),
    patch_allowed=True and minimal fix guidance may be suggested.
    """
    return _analyze_verify_failure(
        project_root=project_root,
        verify_log_path=verify_log_path,
        failed_step=failed_step,
        recent_diff=recent_diff,
        contract_paths=contract_paths,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

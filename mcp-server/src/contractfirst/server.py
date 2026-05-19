"""FastMCP server for the contractfirst checkpoint tools."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .ambiguity import commit_ambiguity_audit as _commit_ambiguity_audit
from .ambiguity import draft_ambiguity_score as _draft_ambiguity_score
from .ambiguity import score_ambiguity as _score_ambiguity
from .failure import analyze_verify_failure as _analyze_verify_failure
from .links import verify_links as _verify_links
from .manual_checks import track_manual_checks as _track_manual_checks
from .verify import run_verify as _run_verify

mcp = FastMCP("contractfirst-mcp")


@mcp.tool()
def run_verify(
    project_root: str,
    scope: str = "full",
    verify_script: str = "./verify.sh",
    feature: str | None = None,
) -> dict[str, Any]:
    """Execute the project's verification suite and return structured results.

    Use this instead of trusting an AI's claim that tests passed. Runs the
    project's verify.sh (passing `scope` as its first argument) or falls back
    to language-detected defaults (npm or pytest/mypy/ruff). Per-step exit
    codes, durations, and truncated logs are returned; full logs are saved
    under .contractfirst/.

    When `feature` is provided, the tool consults the manual-check ledger
    (`track_manual_checks`) for that feature. If any required manual check is
    still pending and automatic checks did not fail, overall is downgraded
    to `pending_manual` so a green automatic run cannot be reported as done
    on ui-heavy / mixed projects.
    """
    return _run_verify(
        project_root=project_root,
        scope=scope,
        verify_script=verify_script,
        feature=feature,
    )


@mcp.tool()
def score_ambiguity(
    goal_clarity: float,
    goal_evidence: str,
    constraint_clarity: float,
    constraint_evidence: str,
    success_criteria_clarity: float,
    success_evidence: str,
    blocking_questions: list[str],
    open_questions: list[str] | None = None,
    project_root: str | None = None,
) -> dict[str, Any]:
    """Compute the ambiguity gate verdict from clarity scores + required evidence.

    Each per-dimension clarity score in [0.0, 1.0] must be accompanied by a
    verbatim quote (>= 8 chars) from the user's request, or the literal
    token "none" to indicate the user said nothing about that dimension.
    The literal "none" forces the score to be <= 0.30 — the AI cannot claim
    high clarity without producing actual evidence. Ambiguity is computed
    deterministically as 1 - (0.4*goal + 0.3*constraint + 0.3*success).
    proceed=true requires ambiguity <= 0.20 AND zero blocking questions.
    The returned report_markdown is the verbatim template the SKILL.md
    Clarification Gate must print, including the evidence quotes so the
    human can judge whether the quote justifies the score.

    Passing `project_root` enables a one-line entry in
    `<project_root>/.contractfirst/gates.jsonl` so the gate decision is
    auditable later.
    """
    return _score_ambiguity(
        goal_clarity=goal_clarity,
        goal_evidence=goal_evidence,
        constraint_clarity=constraint_clarity,
        constraint_evidence=constraint_evidence,
        success_criteria_clarity=success_criteria_clarity,
        success_evidence=success_evidence,
        blocking_questions=blocking_questions,
        open_questions=open_questions,
        project_root=project_root,
    )


@mcp.tool()
def draft_ambiguity_score(
    project_root: str,
    user_prompt_verbatim: str,
    goal_clarity: float,
    goal_evidence: str,
    constraint_clarity: float,
    constraint_evidence: str,
    success_criteria_clarity: float,
    success_evidence: str,
    blocking_questions: list[str],
    open_questions: list[str] | None = None,
) -> dict[str, Any]:
    """Step 1 of the audited two-step ambiguity gate. Stages claims and returns an auditor prompt.

    Agent A submits per-dimension clarity scores with verbatim evidence quotes
    plus the user's original request text. MCP persists the draft to
    `<project_root>/.contractfirst/drafts/<draft_id>.json` and returns an
    auditor_prompt_markdown that Agent A must dispatch to a sub-agent using
    the CLI's native mechanism (Claude Code Task tool, pi -p, codex exec,
    etc.). The returned audit_token must be echoed by the sub-agent verdict
    or commit_ambiguity_audit will reject the transcript.

    Drafts older than 1 hour are auto-purged; at most 50 drafts kept per
    project. Each draft is logged to `.contractfirst/gates.jsonl`.
    """
    return _draft_ambiguity_score(
        project_root=project_root,
        user_prompt_verbatim=user_prompt_verbatim,
        goal_clarity=goal_clarity,
        goal_evidence=goal_evidence,
        constraint_clarity=constraint_clarity,
        constraint_evidence=constraint_evidence,
        success_criteria_clarity=success_criteria_clarity,
        success_evidence=success_evidence,
        blocking_questions=blocking_questions,
        open_questions=open_questions,
    )


@mcp.tool()
def commit_ambiguity_audit(
    project_root: str,
    draft_id: str,
    auditor_transcript: str,
) -> dict[str, Any]:
    """Step 2 of the audited two-step ambiguity gate. Applies the auditor's verdict.

    Loads the draft created by `draft_ambiguity_score`, extracts the first
    JSON object whose `audit_token` matches the stored token from the
    `auditor_transcript`, validates its schema, and forces any dimension
    with `valid: false` to score 0.0 in the final ambiguity calculation.
    proceed=true requires final ambiguity <= 0.20 AND zero blocking
    questions (carried from the draft).

    Required verdict schema (echoed by the sub-agent):
        {
          "audit_token": "<token from draft response>",
          "dimensions": {
            "goal":       {"valid": bool, "reason": "..."},
            "constraint": {"valid": bool, "reason": "..."},
            "success":    {"valid": bool, "reason": "..."}
          }
        }

    Tampering surfaces: missing audit_token, malformed JSON, or schema
    violations are rejected as errors (the draft is NOT consumed — Agent A
    may retry). Successful parsing consumes the draft (single-shot, to
    prevent verdict brute-forcing). Every call appends one line to
    `.contractfirst/gates.jsonl`.
    """
    return _commit_ambiguity_audit(
        project_root=project_root,
        draft_id=draft_id,
        auditor_transcript=auditor_transcript,
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

    Folder resolution order: per-call `link_dirs` > `<project_root>/
    .contractfirst/config.json` ("link_dirs") > built-in defaults.
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

    Classification (contract_sensitive vs routine) is layered:
      1. failed_step == "test" → always contract_sensitive.
      2. Any suspected file in contract dirs/conventions
         (specs/, invariants/, interfaces/, tests/, *.spec.*, *_test.*).
      3. Multi-framework structured failure markers (pytest, Jest/Vitest,
         RSpec, Go test, Rust, NUnit/xUnit, ExUnit).
      4. lint/format steps default to routine unless 1-3 say otherwise.

    For contract_sensitive failures the H4 gate forbids a patch
    (patch_allowed=False) — the human must approve a fix strategy first.
    Returns the signals that triggered the classification, so the human
    can audit the decision.
    """
    return _analyze_verify_failure(
        project_root=project_root,
        verify_log_path=verify_log_path,
        failed_step=failed_step,
        recent_diff=recent_diff,
        contract_paths=contract_paths,
    )


@mcp.tool()
def track_manual_checks(
    project_root: str,
    feature: str,
    op: str = "summary",
    checks: list[dict[str, Any]] | None = None,
    check_id: str | None = None,
    note: str | None = None,
    replace: bool = False,
) -> dict[str, Any]:
    """Declare and confirm manual verification items per feature.

    `run_verify(feature=...)` consults this ledger and refuses to return
    `overall: pass` while required manual checks are still pending. This
    closes the ui-heavy verification gap: an all-green `verify.sh` is not
    sufficient when SKILL.md's project type is `ui-heavy` or `mixed`.

    Operations:
      declare  — create/append checks. `checks` is a list of
                 {id, description, required?}. Use `replace=True` to
                 reset the ledger.
      confirm  — mark `check_id` as confirmed by the human.
      handoff  — mark `check_id` as explicitly handed off (still counts
                 as resolved).
      list     — return the full ledger.
      summary  — return only the summary block (default).

    Ledger persisted at `<project_root>/.contractfirst/manual-checks/<feature>.json`.
    """
    return _track_manual_checks(
        project_root=project_root,
        feature=feature,
        op=op,
        checks=checks,
        check_id=check_id,
        note=note,
        replace=replace,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

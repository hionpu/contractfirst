"""analyze_verify_failure: structured root-cause hypotheses without proposing patches."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

CONTRACT_KEYWORDS = (
    "invariant",
    "interface",
    "protocol",
    "contract",
    "spec",
    "assertion",
    "assert",
    "expected",
    "got",
    "should",
)

ROUTINE_STEPS = {"lint", "format"}
ALWAYS_CONTRACT_STEPS = {"test"}

ERROR_LINE_RE = re.compile(
    r"^(.*(?:error|fail|traceback|assertionerror|exception|warning|\b[A-Z]\d{3,4}\b).*)$",
    re.IGNORECASE | re.MULTILINE,
)

# Common file-path-with-line patterns: foo/bar.py:42, foo/bar.ts(10,5), foo/bar.js:10:5
FILE_REF_RE = re.compile(
    r"([A-Za-z_][\w./\\-]*\.(?:py|ts|tsx|js|jsx|go|rs|java|rb|md))[:(]\s*(\d+)"
)

INVARIANT_TAG_RE = re.compile(r"\b(INV-\d+)\b")


def _read_log(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _is_scaffolding(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    if set(s) <= {"=", "-", "_"}:
        return True
    return s.startswith(
        ("status:", "exit_code:", "duration:", "scope:", "timestamp:", "## ", "# ", "--- ", "===", "___")
    )


def _rank_error_line(line: str) -> int:
    low = line.lower()
    score = 0
    if any(
        cls in line
        for cls in ("AssertionError", "TypeError", "AttributeError", "ValueError",
                    "ImportError", "ModuleNotFoundError", "RuntimeError", "Exception")
    ):
        score += 100
    if "error:" in low or ": error" in low:
        score += 50
    if "traceback" in low:
        score += 30
    if "expected" in low and "got" in low:
        score += 20
    if "fail" in low and not any(w in low for w in ("error", "exception", "traceback", "assert")):
        score -= 50
    return score


def _extract_error_lines(log: str, limit: int = 20) -> list[str]:
    raw = [m.group(1).strip() for m in ERROR_LINE_RE.finditer(log)]
    seen: set[str] = set()
    filtered: list[str] = []
    for ln in raw:
        if not ln or _is_scaffolding(ln) or ln in seen:
            continue
        seen.add(ln)
        filtered.append(ln)
    filtered.sort(key=_rank_error_line, reverse=True)
    return filtered[:limit]


def _summarize_errors(error_lines: list[str]) -> str:
    if not error_lines:
        return "no error lines detected in log"
    primary = error_lines[0]
    if len(primary) > 240:
        primary = primary[:237] + "..."
    return primary


def _extract_suspected_files(log: str, project_root: Path, limit: int = 8) -> list[str]:
    matches: list[str] = []
    seen: set[str] = set()
    for m in FILE_REF_RE.finditer(log):
        rel = m.group(1).replace("\\", "/")
        if rel in seen:
            continue
        candidate = (project_root / rel).resolve()
        if candidate.exists():
            seen.add(rel)
            matches.append(rel)
        else:
            if rel not in seen:
                seen.add(rel)
                matches.append(rel)
        if len(matches) >= limit:
            break
    return matches


def _is_contract_sensitive(failed_step: str, log: str, suspected_files: list[str]) -> bool:
    step = failed_step.lower()
    if step in ALWAYS_CONTRACT_STEPS:
        return True
    if step in ROUTINE_STEPS:
        return False
    low = log.lower()
    if any(kw in low for kw in CONTRACT_KEYWORDS):
        return True
    contract_path_hints = ("invariants/", "interfaces/", "specs/", "/tests/", "test_")
    return any(any(h in f for h in contract_path_hints) for f in suspected_files)


def _find_violated_invariant(log: str, contract_paths: list[str] | None, root: Path) -> str | None:
    direct = INVARIANT_TAG_RE.search(log)
    if direct:
        return direct.group(1)
    if not contract_paths:
        return None
    for rel in contract_paths:
        p = (root / rel).resolve()
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        tags = INVARIANT_TAG_RE.findall(text)
        for tag in tags:
            if tag in log:
                return tag
    return None


def _hypotheses(
    category: str,
    failed_step: str,
    error_lines: list[str],
    suspected_files: list[str],
    violated_invariant: str | None,
) -> list[dict[str, Any]]:
    if not error_lines:
        return []
    primary = error_lines[0]
    low = primary.lower()
    hyps: list[dict[str, Any]] = []

    if "assertion" in low or "assertionerror" in low or ("expected" in low and "got" in low):
        hyps.append(
            {
                "description": "An assertion failed: the observed value does not match the expected value declared by the test contract.",
                "evidence": primary,
                "violated_invariant": violated_invariant,
            }
        )
    if "typeerror" in low or "type error" in low or low.startswith("error:") and "type" in low:
        hyps.append(
            {
                "description": "Type mismatch: a value flowing through this path does not satisfy the declared interface signature.",
                "evidence": primary,
                "violated_invariant": violated_invariant,
            }
        )
    if "attributeerror" in low or "has no attribute" in low:
        hyps.append(
            {
                "description": "A symbol referenced in code does not exist on the target — interface drift between caller and callee.",
                "evidence": primary,
                "violated_invariant": violated_invariant,
            }
        )
    if "importerror" in low or "modulenotfounderror" in low:
        hyps.append(
            {
                "description": "Import target is missing or renamed — module boundary likely changed without updating callers.",
                "evidence": primary,
                "violated_invariant": None,
            }
        )
    if not hyps:
        hyps.append(
            {
                "description": "Verification produced an error whose category is unclear from the log alone; inspect the surrounding context.",
                "evidence": primary,
                "violated_invariant": violated_invariant,
            }
        )

    if category == "routine" and suspected_files:
        hyps[0]["evidence"] = hyps[0]["evidence"] + f" (suspect: {suspected_files[0]})"
    return hyps


def _fix_strategy_options(category: str, failed_step: str, error_lines: list[str]) -> list[str]:
    if not error_lines:
        return []
    primary = error_lines[0].lower()
    if category == "routine":
        if failed_step.lower() == "lint":
            return [
                "Apply the linter's suggested fix at the reported location",
                "Update the lint config only if the rule is misapplied to this codebase",
            ]
        if "type" in primary:
            return [
                "Narrow or correct the type annotation at the reported call site",
                "Adjust the function signature if the caller contract changed intentionally",
            ]
        return ["Apply the minimal correction at the reported location"]
    options: list[str] = []
    if "assertion" in primary or "expected" in primary:
        options.append("Decide whether the test or the implementation encodes the correct invariant, then update the wrong side")
        options.append("If the invariant itself is wrong, open a contract change rather than mutating the test")
    if "type" in primary:
        options.append("Reconcile the interface signature with its actual usage in callers and implementations")
    if "import" in primary or "attribute" in primary:
        options.append("Restore the missing symbol, or update all callers and the interface contract together")
    if not options:
        options.append("Identify which contract (spec, invariant, interface, test) is being violated before changing code")
    return options


def analyze_verify_failure(
    project_root: str,
    verify_log_path: str,
    failed_step: str,
    recent_diff: str | None = None,
    contract_paths: list[str] | None = None,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    log_file = Path(verify_log_path)
    if not log_file.is_absolute():
        log_file = (root / verify_log_path).resolve()
    log = _read_log(log_file)

    error_lines = _extract_error_lines(log)
    suspected = _extract_suspected_files(log, root)
    category = (
        "contract_sensitive"
        if _is_contract_sensitive(failed_step, log, suspected)
        else "routine"
    )
    violated = _find_violated_invariant(log, contract_paths, root)
    hyps = _hypotheses(category, failed_step, error_lines, suspected, violated)
    strategies = _fix_strategy_options(category, failed_step, error_lines)

    patch_allowed = category == "routine"
    h4_reason = (
        "routine failure: AI may apply a minimal fix at the reported location"
        if patch_allowed
        else "contract_sensitive failure: human must approve fix strategy before AI writes the patch"
    )

    result: dict[str, Any] = {
        "category": category,
        "failed_step": failed_step,
        "error_summary": _summarize_errors(error_lines),
        "suspected_files": suspected,
        "hypotheses": hyps,
        "fix_strategy_options": strategies,
        "h4_gate": {
            "patch_allowed": patch_allowed,
            "reason": h4_reason,
        },
    }
    if recent_diff:
        result["recent_diff_considered"] = True
    return result

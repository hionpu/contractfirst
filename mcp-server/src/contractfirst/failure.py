"""analyze_verify_failure: structured root-cause hypotheses without proposing patches.

Classification (contract_sensitive vs routine) drives the H4 gate in
SKILL.md: contract_sensitive failures set patch_allowed=False, meaning the
AI must surface the root cause and wait for the human to approve a fix
strategy before writing any patch.

Detection is layered, strongest to weakest:
  1. Step-based: failed_step == "test" → always contract_sensitive.
  2. Path-based: any suspected file in contract dirs/conventions
     (specs/, invariants/, interfaces/, tests/, *.spec.*, *_test.*, test_*).
  3. Framework-aware exception detection: structured patterns from pytest,
     unittest, Jest/Vitest, Mocha/Chai, RSpec, Go test, Rust assert,
     NUnit/xUnit. These are class/marker patterns, NOT keyword guesses.
  4. Routine steps: lint, format → routine unless paths/exception say otherwise.
  5. Fallback: natural-language keyword scan (weakest signal).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .gatelog import append_gate_event

ROUTINE_STEPS = {"lint", "format"}
ALWAYS_CONTRACT_STEPS = {"test"}

CONTRACT_PATH_HINTS = (
    "docs/specs/",
    "docs/invariants/",
    "invariants/",
    "interfaces/",
    "specs/",
    "/tests/",
    "tests/",
    "/test/",
)
CONTRACT_FILENAME_RE = re.compile(
    r"(?:^|/)(?:test_[^/]+|[^/]+_test\.[a-z]+|[^/]+\.(?:spec|test)\.[a-z]+)$",
    re.IGNORECASE,
)

# Multi-framework structured failure markers. These are deliberately specific
# (class names, framework prefixes) rather than free-text keywords so they
# do not fire on incidental words like "should" or "expected" in stdout.
STRUCTURED_FAILURE_PATTERNS = (
    # Python (pytest, unittest)
    re.compile(r"\bAssertionError\b"),
    re.compile(r"^E\s+AssertionError\b", re.MULTILINE),
    re.compile(r"^E\s+assert\b", re.MULTILINE),
    re.compile(r"\bFAILED\s+\S+::\S+"),               # pytest summary
    # JS/TS (Jest, Vitest, Mocha, Chai)
    re.compile(r"\bexpect\([^)]*\)\.(?:to|not|toBe|toEqual|toMatch)"),
    re.compile(r"^\s*●\s+\S+", re.MULTILINE),         # Jest failure header
    re.compile(r"^\s*FAIL\s+\S+\.(?:spec|test)\.", re.MULTILINE),
    re.compile(r"^\s*✗\s+", re.MULTILINE),            # Vitest/Mocha failure mark
    re.compile(r"AssertionError\s*\[ERR_ASSERTION\]"),  # node:assert
    # Ruby (RSpec, Minitest)
    re.compile(r"^Failure/Error:", re.MULTILINE),
    re.compile(r"\bRSpec::Expectations::ExpectationNotMetError\b"),
    re.compile(r"\bMinitest::Assertion\b"),
    # Go
    re.compile(r"^---\s+FAIL:\s+\S+", re.MULTILINE),
    re.compile(r"^\s*panic:\s+", re.MULTILINE),
    # Rust
    re.compile(r"assertion (?:failed|`[^`]+` failed)"),
    re.compile(r"thread '\S+' panicked at"),
    # .NET (xUnit, NUnit)
    re.compile(r"\bXunit\.Sdk\.\w*Exception\b"),
    re.compile(r"\bNUnit\.Framework\.AssertionException\b"),
    re.compile(r"^\s*Expected:\s+.*\n\s*But was:", re.MULTILINE),
    # Elixir (ExUnit)
    re.compile(r"^\s*\d+\)\s+test\s+", re.MULTILINE),
    re.compile(r"\bAssertion with == failed\b"),
    # Type/interface drift signals (treated as contract-sensitive when surfaced
    # from any framework that prints them)
    re.compile(r"\b(?:TypeError|AttributeError|NameError)\b"),
    re.compile(r"\b(?:ImportError|ModuleNotFoundError)\b"),
    # Explicit invariant tag
    re.compile(r"\bINV-\d+\b"),
)

# Generic error-line extraction. The classifier no longer leans on this for
# contract-sensitivity; it is only used to surface evidence to the human.
ERROR_LINE_RE = re.compile(
    r"^(.*(?:error|fail|traceback|assertionerror|exception|warning|\b[A-Z]\d{3,4}\b).*)$",
    re.IGNORECASE | re.MULTILINE,
)
FILE_REF_RE = re.compile(
    r"([A-Za-z_][\w./\\-]*\.(?:py|ts|tsx|js|jsx|go|rs|java|rb|cs|ex|exs|lua|luau|md))[:(]\s*(\d+)"
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
        for cls in (
            "AssertionError", "TypeError", "AttributeError", "ValueError",
            "ImportError", "ModuleNotFoundError", "RuntimeError", "Exception",
            "RSpec::Expectations", "Xunit.Sdk", "NUnit.Framework",
        )
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
        seen.add(rel)
        matches.append(rel)
        if len(matches) >= limit:
            break
    return matches


def _path_signal_contract(suspected_files: list[str]) -> bool:
    for f in suspected_files:
        norm = "/" + f.replace("\\", "/").lstrip("/")
        if any(h in norm for h in CONTRACT_PATH_HINTS):
            return True
        if CONTRACT_FILENAME_RE.search(norm):
            return True
    return False


def _structured_signal_contract(log: str) -> tuple[bool, str | None]:
    for pat in STRUCTURED_FAILURE_PATTERNS:
        m = pat.search(log)
        if m:
            return True, pat.pattern
    return False, None


def _classify(failed_step: str, log: str, suspected_files: list[str]) -> tuple[str, list[str]]:
    """Return (category, signals). Signals are why we classified that way."""
    step = failed_step.lower()
    signals: list[str] = []

    if step in ALWAYS_CONTRACT_STEPS:
        signals.append(f"step:{step}")
        return "contract_sensitive", signals

    if _path_signal_contract(suspected_files):
        signals.append("path:contract-dir")
        return "contract_sensitive", signals

    matched, pattern = _structured_signal_contract(log)
    if matched:
        signals.append(f"structured:{pattern}")
        return "contract_sensitive", signals

    if step in ROUTINE_STEPS:
        signals.append(f"step:{step}")
        return "routine", signals

    signals.append("fallback:no-signal")
    return "routine", signals


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
    category, signals = _classify(failed_step, log, suspected)
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
        "classification_signals": signals,
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

    append_gate_event(
        root,
        "analyze_verify_failure",
        {
            "failed_step": failed_step,
            "category": category,
            "signals": signals,
            "patch_allowed": patch_allowed,
            "violated_invariant": violated,
        },
    )
    return result

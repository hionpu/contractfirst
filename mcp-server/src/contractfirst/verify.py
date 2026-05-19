"""run_verify: execute project verification suite, capture structured results."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .gatelog import append_gate_event
from .manual_checks import read_summary as _read_manual_summary

STEP_TIMEOUT_SECONDS = 300
TAIL_LIMIT = 2000
VALID_SCOPES = ("full", "typecheck", "test", "lint", "build")

NODE_DEFAULTS = {
    "typecheck": ["npm", "run", "typecheck"],
    "test": ["npm", "test", "--", "--watch=false"],
    "lint": ["npm", "run", "lint"],
    "build": ["npm", "run", "build"],
}

PYTHON_DEFAULTS = {
    "typecheck": ["mypy", "."],
    "test": ["pytest", "-q"],
    "lint": ["ruff", "check", "."],
    "build": None,
}


def _tail(text: str, limit: int = TAIL_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _exec(cmd: list[str] | str, cwd: Path, shell: bool = False) -> tuple[int, str, str, float]:
    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            shell=shell,
            capture_output=True,
            text=True,
            timeout=STEP_TIMEOUT_SECONDS,
            check=False,
        )
        duration = time.monotonic() - start
        return proc.returncode, proc.stdout or "", proc.stderr or "", duration
    except subprocess.TimeoutExpired as e:
        duration = time.monotonic() - start
        return 124, e.stdout or "", (e.stderr or "") + f"\n[timeout after {STEP_TIMEOUT_SECONDS}s]", duration
    except FileNotFoundError as e:
        duration = time.monotonic() - start
        return -1, "", f"command not found: {e}", duration


def _step(name: str, status: str, exit_code: int, duration: float, stdout: str, stderr: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "exit_code": exit_code,
        "duration_seconds": round(duration, 2),
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
    }


def _node_scripts(root: Path) -> dict[str, Any]:
    pkg = root / "package.json"
    if not pkg.is_file():
        return {}
    try:
        return json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {}) or {}
    except (OSError, json.JSONDecodeError):
        return {}


def _run_node_step(root: Path, scripts: dict[str, Any], step: str) -> dict[str, Any]:
    if step == "test":
        cmd = NODE_DEFAULTS["test"]
    elif step in scripts:
        cmd = NODE_DEFAULTS[step]
    else:
        return _step(step, "not_configured", -1, 0.0, "", f"no '{step}' script in package.json")
    code, out, err, dur = _exec(cmd, root, shell=False)
    status = "pass" if code == 0 else "fail"
    return _step(step, status, code, dur, out, err)


def _run_python_step(root: Path, step: str) -> dict[str, Any]:
    cmd = PYTHON_DEFAULTS.get(step)
    if cmd is None:
        return _step(step, "not_configured", -1, 0.0, "", f"no default for python '{step}'")
    if shutil.which(cmd[0]) is None:
        return _step(step, "not_configured", -1, 0.0, "", f"tool not installed: {cmd[0]}")
    code, out, err, dur = _exec(cmd, root, shell=False)
    status = "pass" if code == 0 else "fail"
    return _step(step, status, code, dur, out, err)


def _detect_steps(scope: str) -> list[str]:
    if scope == "full":
        return ["typecheck", "test", "lint", "build"]
    return [scope]


def _run_language_defaults(root: Path, scope: str) -> list[dict[str, Any]]:
    steps_to_run = _detect_steps(scope)
    is_node = (root / "package.json").is_file()
    is_python = (root / "pyproject.toml").is_file()

    if not (is_node or is_python):
        return [
            _step(
                s,
                "not_configured",
                -1,
                0.0,
                "",
                "no verify_script and no recognized project type",
            )
            for s in steps_to_run
        ]

    if is_node:
        scripts = _node_scripts(root)
        return [_run_node_step(root, scripts, s) for s in steps_to_run]
    return [_run_python_step(root, s) for s in steps_to_run]


def _run_verify_script(script: Path, scope: str, root: Path) -> list[dict[str, Any]]:
    use_shell = script.suffix.lower() in (".sh", ".bash") and script.exists()
    cmd_list: list[str] | str
    if use_shell:
        cmd_list = f'"{script}" {scope}'
        code, out, err, dur = _exec(cmd_list, root, shell=True)
    else:
        cmd_list = [str(script), scope]
        code, out, err, dur = _exec(cmd_list, root, shell=False)
    status = "pass" if code == 0 else "fail"
    return [_step(f"verify_script({scope})", status, code, dur, out, err)]


def _overall(steps: list[dict[str, Any]]) -> str:
    statuses = {s["status"] for s in steps}
    if "fail" in statuses:
        return "fail"
    if statuses <= {"pass"}:
        return "pass"
    if "pass" in statuses:
        return "partial"
    return "partial"


def _apply_manual_gate(automatic_overall: str, manual: dict[str, Any] | None) -> tuple[str, str | None]:
    """Combine the automatic verdict with the manual-check ledger.

    Returns (overall, reason). When manual is None or has no required pending,
    overall is unchanged. When required pending exists and automatic !=fail,
    overall becomes `pending_manual` to block a green report.
    """
    if manual is None:
        return automatic_overall, None
    if manual["all_required_resolved"]:
        return automatic_overall, None
    if automatic_overall == "fail":
        return "fail", None
    pending = ", ".join(manual["pending_ids"]) or "unspecified"
    return "pending_manual", f"manual checks pending: {pending}"


def _write_log(log_path: Path, scope: str, steps: list[dict[str, Any]], full_outputs: list[tuple[str, str, str]]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# contractfirst verify log", f"# scope: {scope}", f"# timestamp: {datetime.now().isoformat()}", ""]
    for step, (name, out, err) in zip(steps, full_outputs):
        lines.append(f"## step: {name}")
        lines.append(f"status: {step['status']}  exit_code: {step['exit_code']}  duration: {step['duration_seconds']}s")
        lines.append("--- stdout ---")
        lines.append(out)
        lines.append("--- stderr ---")
        lines.append(err)
        lines.append("")
    log_path.write_text("\n".join(lines), encoding="utf-8")


def run_verify(
    project_root: str,
    scope: str = "full",
    verify_script: str = "./verify.sh",
    feature: str | None = None,
) -> dict[str, Any]:
    if scope not in VALID_SCOPES:
        raise ValueError(f"scope must be one of {VALID_SCOPES}, got {scope!r}")
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise ValueError(f"project_root is not a directory: {project_root}")

    script = (root / verify_script).resolve()
    if script.is_file():
        full_outputs: list[tuple[str, str, str]] = []
        steps = _run_verify_script(script, scope, root)
        for s in steps:
            full_outputs.append((s["name"], s["stdout_tail"], s["stderr_tail"]))
    else:
        steps = _run_language_defaults(root, scope)
        full_outputs = [(s["name"], s["stdout_tail"], s["stderr_tail"]) for s in steps]

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = root / ".contractfirst" / f"verify-{timestamp}.log"
    try:
        _write_log(log_path, scope, steps, full_outputs)
        log_path_str = str(log_path)
    except OSError as e:
        log_path_str = f"<log write failed: {e}>"

    failed = [s["name"] for s in steps if s["status"] == "fail"]
    passed = [s for s in steps if s["status"] == "pass"]
    summary = f"{len(passed)}/{len(steps)} passed"
    if failed:
        summary += f", {len(failed)} failed ({', '.join(failed)})"

    automatic_overall = _overall(steps)
    manual_summary = _read_manual_summary(root, feature) if feature else None
    overall, manual_reason = _apply_manual_gate(automatic_overall, manual_summary)
    if manual_reason:
        summary += f"; {manual_reason}"

    result: dict[str, Any] = {
        "overall": overall,
        "automatic_overall": automatic_overall,
        "scope_executed": scope,
        "steps": steps,
        "summary": summary,
        "failed_step_names": failed,
        "log_path": log_path_str,
        "feature": feature,
        "manual_checks": manual_summary,
    }
    append_gate_event(
        root,
        "run_verify",
        {
            "scope": scope,
            "feature": feature,
            "overall": overall,
            "automatic_overall": automatic_overall,
            "failed_step_names": failed,
            "manual_pending_ids": (manual_summary or {}).get("pending_ids", []),
        },
    )
    return result

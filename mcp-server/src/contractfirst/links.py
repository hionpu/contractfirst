"""verify_links: cross-reference checker for spec/invariant/interface/test files.

Resolution order for `link_dirs`:
    1. Per-call `link_dirs` argument (highest priority).
    2. `<project_root>/.contractfirst/config.json` -> "link_dirs".
    3. Built-in defaults.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DEFAULT_LINK_DIRS = {
    "specs": "docs/specs",
    "invariants": "docs/invariants",
    "interfaces": "src/**/interfaces",
    "tests": "tests",
}
CONFIG_RELPATH = ".contractfirst/config.json"


def _load_config_link_dirs(root: Path) -> dict[str, str]:
    cfg = root / CONFIG_RELPATH
    if not cfg.is_file():
        return {}
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    raw = data.get("link_dirs") if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if isinstance(k, str) and isinstance(v, str)}

MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
LINKS_HEADING_RE = re.compile(r"^##+\s+Links\s*$", re.IGNORECASE | re.MULTILINE)
LINKS_BLOCK_RE = re.compile(
    r"<!--\s*LINKS\s*-->\s*(.*?)\s*<!--\s*/LINKS\s*-->",
    re.IGNORECASE | re.DOTALL,
)
LINKS_BARE_OPEN_RE = re.compile(
    r"^[ \t]*<!--\s*Links\s*-->[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _extract_bare_links_section(text: str) -> str | None:
    m = LINKS_BARE_OPEN_RE.search(text)
    if not m:
        return None
    tail = text[m.end():]
    lines = tail.splitlines()
    collected: list[str] = []
    # Skip leading blank line(s) immediately after the comment
    started = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- "):
            collected.append(line)
            started = True
            continue
        if started:
            # First non-list line after the block ends collection
            break
        if stripped == "":
            # Allow a blank line between the comment and the first list item
            continue
        # First non-blank, non-list line before any list item — not a links block we recognize
        break
    return "\n".join(collected)


def _extract_links_section(text: str) -> str:
    # Priority: bare <!-- Links --> → paired <!-- LINKS --> ... <!-- /LINKS --> → ## Links heading
    bare = _extract_bare_links_section(text)
    if bare:
        return bare
    block = LINKS_BLOCK_RE.search(text)
    if block:
        return block.group(1)
    m = LINKS_HEADING_RE.search(text)
    if not m:
        return ""
    tail = text[m.end():]
    next_heading = re.search(r"^##\s+\S", tail, re.MULTILINE)
    return tail[: next_heading.start()] if next_heading else tail


def _extract_link_targets(text: str) -> list[str]:
    section = _extract_links_section(text)
    if not section:
        return []
    targets: list[str] = []
    # For each line, strip leading "- Category:" prefix if present so we only see the values,
    # then extract markdown link targets. "(this file)" is intentionally never captured
    # because it has no markdown-link form.
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Drop "- " prefix and optional "Label:" segment
        if stripped.startswith("- "):
            stripped = stripped[2:].lstrip()
        if ":" in stripped:
            # Only strip the label up to the first colon if what follows looks like values
            head, _, rest = stripped.partition(":")
            # A label is a short word (no spaces) like "Specs", "Invariants", "Tests", "Interfaces"
            if head and " " not in head and len(head) <= 32:
                stripped = rest.strip()
        for m in MD_LINK_RE.finditer(stripped):
            targets.append(m.group(1))
    if targets:
        return targets
    # Fallback: scan the whole section for any markdown links
    return [m.group(1) for m in MD_LINK_RE.finditer(section)]


def _resolve(project_root: Path, ref: str, source_file: Path) -> Path:
    candidate = (source_file.parent / ref).resolve()
    if candidate.exists():
        return candidate
    return (project_root / ref).resolve()


def _spec_back_link_targets(text: str) -> set[str]:
    """All markdown link targets anywhere in the file (used to detect back-links)."""
    return {m.group(1) for m in MD_LINK_RE.finditer(text)}


def _path_matches_ref(target_path: Path, ref: str, project_root: Path) -> bool:
    """A reciprocal link counts if its target resolves to the same file."""
    try:
        candidate = (project_root / ref).resolve()
        if candidate == target_path:
            return True
    except OSError:
        pass
    for source_dir in [target_path.parent, project_root]:
        try:
            if (source_dir / ref).resolve() == target_path:
                return True
        except OSError:
            continue
    name_match = Path(ref).name == target_path.name
    return name_match and target_path.name in ref


def _glob_files(project_root: Path, pattern: str) -> list[Path]:
    if "*" in pattern:
        return [p for p in project_root.glob(pattern) if p.is_dir()]
    full = project_root / pattern
    return [full] if full.is_dir() else []


def _collect_files(project_root: Path, pattern: str, exts: tuple[str, ...]) -> list[Path]:
    result: list[Path] = []
    for d in _glob_files(project_root, pattern):
        for ext in exts:
            result.extend(p for p in d.rglob(f"*{ext}") if p.is_file())
    return result


def verify_links(
    project_root: str,
    feature: str | None = None,
    link_dirs: dict[str, str] | None = None,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    config_dirs = _load_config_link_dirs(root)
    dirs = {**DEFAULT_LINK_DIRS, **config_dirs, **(link_dirs or {})}
    specs_dir = root / dirs["specs"]

    if not specs_dir.is_dir():
        return {
            "feature": feature,
            "checked_files": 0,
            "status": "not_configured",
            "missing": [],
            "stale": [],
            "orphaned": [],
            "summary": f"specs directory not found: {dirs['specs']}",
        }

    spec_files = sorted(p for p in specs_dir.rglob("*.md") if p.is_file())
    if feature:
        spec_files = [p for p in spec_files if feature in p.stem or feature in str(p.parent)]

    missing: list[dict[str, str]] = []
    stale: list[dict[str, str]] = []
    referenced: set[Path] = set()

    for spec in spec_files:
        spec_text = _read(spec)
        spec_rel = spec.relative_to(root).as_posix()
        for ref in _extract_link_targets(spec_text):
            target = _resolve(root, ref, spec)
            if not target.exists():
                missing.append(
                    {"from": spec_rel, "to": ref, "reason": "file not found"}
                )
                continue
            referenced.add(target)
            target_text = _read(target)
            back_refs = _spec_back_link_targets(target_text)
            if not any(_path_matches_ref(spec, br, root) for br in back_refs):
                stale.append(
                    {
                        "from": spec_rel,
                        "to": target.relative_to(root).as_posix(),
                        "reason": "no back-link",
                    }
                )

    orphaned: list[dict[str, str]] = []
    if not feature:
        candidates: list[Path] = []
        candidates.extend(_collect_files(root, dirs["invariants"], (".md",)))
        candidates.extend(
            _collect_files(root, dirs["interfaces"], (".ts", ".py", ".js", ".md"))
        )
        candidates.extend(
            _collect_files(root, dirs["tests"], (".py", ".ts", ".js"))
        )
        for path in candidates:
            if path not in referenced:
                orphaned.append(
                    {
                        "path": path.relative_to(root).as_posix(),
                        "reason": "not referenced by any spec",
                    }
                )

    status = "complete" if not (missing or stale or orphaned) else "incomplete"
    summary = f"{len(missing)} missing, {len(stale)} stale, {len(orphaned)} orphaned"
    return {
        "feature": feature,
        "checked_files": len(spec_files),
        "status": status,
        "missing": missing,
        "stale": stale,
        "orphaned": orphaned,
        "summary": summary,
    }

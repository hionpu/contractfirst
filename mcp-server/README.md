# contractfirst

> Python package name: `contractfirst`. MCP server registration name (what you pass to `claude mcp add` / config files): `contractfirst`.

An MCP server that provides **deterministic, non-bypassable checkpoints** for the [`contractfirst`](https://github.com/hionpu/contractfirst) workflow. The `contractfirst` skill is a prompt — when context drifts, the model can ignore it. This server exposes five tools whose outputs are externally verifiable: if the AI claims tests passed, you can re-run the same tool on the same inputs and falsify the claim.

Scope is deliberately narrow. File-write guards, contract-change workflows, plan gates, and human-zone tracking live elsewhere (OS permissions, Git, the skill prompt). This server only handles the parts the AI is most likely to fake or skip.

## The seven tools

| Tool | Replaces this AI failure mode |
|------|-------------------------------|
| `run_verify` | "Tests passed" — when they didn't, or weren't actually run |
| `score_ambiguity` | "The spec is clear enough" — AI grading its own homework (single-call, evidence-required) |
| `draft_ambiguity_score` | Self-confirming a clarity score with no second opinion (Step 1 of audited two-step) |
| `commit_ambiguity_audit` | Skipping or rubber-stamping the auditor (Step 2 — token-gated verdict parse) |
| `verify_links` | "Links are complete" — without actually checking files |
| `analyze_verify_failure` | Patching before understanding root cause |
| `track_manual_checks` | "Done" reported on ui-heavy work while manual playtest items are still pending |

Every gate decision (proceed/no, patch_allowed, overall, manual-check resolution) appends one JSON line to `<project_root>/.contractfirst/gates.jsonl` for after-the-fact audit.

## Install

```bash
pip install -e .
# or
uv pip install -e .
```

Requires Python 3.11+.

## Register

**Claude Code**

```bash
claude mcp add contractfirst -- python -m contractfirst.server
```

**Codex CLI** (`~/.codex/config.toml`)

```toml
[mcp_servers.contractfirst]
command = "python"
args = ["-m", "contractfirst.server"]
```

Both clients launch the server over stdio.

## Example calls

### `run_verify`

```jsonc
{
  "project_root": "/path/to/repo",
  "scope": "full",
  "verify_script": "./verify.sh",
  "feature": "minigame-ui"          // optional — consults manual-check ledger
}
```

Runs `./verify.sh full` if the script exists; otherwise falls back to language-detected defaults (`npm run typecheck/test/lint/build` for Node, `mypy . / pytest / ruff check .` for Python). Full logs are written under `<project_root>/.contractfirst/verify-<timestamp>.log`; the truncated tail (last 2000 chars per stream) is returned inline.

When `feature` is provided, the tool reads the manual-check ledger for that feature. If any required manual check is still pending and automatic checks did not fail, `overall` is downgraded to `pending_manual` — a green automatic run cannot be reported as done on ui-heavy / mixed projects.

### `score_ambiguity`

```jsonc
{
  "goal_clarity": 0.9,
  "goal_evidence": "user said: 'show top 10 players by score'",
  "constraint_clarity": 0.4,
  "constraint_evidence": "none",
  "success_criteria_clarity": 0.8,
  "success_evidence": "user said: 'verify by API returning sorted array'",
  "blocking_questions": [],
  "open_questions": ["Should we cache responses?"],
  "project_root": "/path/to/repo"   // optional — enables gates.jsonl entry
}
```

Weights are fixed at 0.40 / 0.30 / 0.30. Each clarity score must be paired with a verbatim quote from the user's request (≥ 8 chars), or the literal token `"none"` if the user said nothing about that dimension — `"none"` then forces the score to be ≤ 0.30, so the AI cannot claim high clarity without producing actual evidence. `proceed: true` only when `ambiguity <= 0.20` and `blocking_questions` is empty. The returned `report_markdown` is the verbatim template the skill expects to print, including the evidence quotes.

### `draft_ambiguity_score` + `commit_ambiguity_audit` (audited two-step)

Stronger variant of `score_ambiguity`: forces a second-opinion sub-agent audit before the gate decision is finalized. Agent A cannot self-confirm. Two calls per gate.

**Step 1 — draft:**

```jsonc
{
  "project_root": "/path/to/repo",
  "user_prompt_verbatim": "Implement login. Must use OAuth. Verify by signing in with Google.",
  "goal_clarity": 0.9,
  "goal_evidence": "Implement login",
  "constraint_clarity": 0.8,
  "constraint_evidence": "Must use OAuth",
  "success_criteria_clarity": 0.85,
  "success_evidence": "Verify by signing in with Google",
  "blocking_questions": [],
  "open_questions": []
}
```

Returns `{ draft_id, audit_token, auditor_prompt_markdown, next_action }`. The draft is persisted at `<project_root>/.contractfirst/drafts/<draft_id>.json`. TTL 1 hour; cap 50 drafts per project.

The caller then dispatches a sub-agent with `auditor_prompt_markdown` using its CLI's native mechanism (Claude Code `Task` tool / `pi -p` / `codex exec`).

**Step 2 — commit:**

```jsonc
{
  "project_root": "/path/to/repo",
  "draft_id": "ab12cd34ef56",
  "auditor_transcript": "...sub-agent's full text output, verbatim..."
}
```

MCP extracts the first JSON object containing the matching `audit_token` from the transcript. Required verdict schema:

```json
{
  "audit_token": "<token from draft response>",
  "dimensions": {
    "goal":       {"valid": true,  "reason": "..."},
    "constraint": {"valid": false, "reason": "..."},
    "success":    {"valid": true,  "reason": "..."}
  }
}
```

Any dimension with `valid: false` has its score forced to 0.0 in the final calculation. Token mismatch, malformed JSON, or schema violation → error (draft NOT consumed, retryable). Successful parse consumes the draft (single-shot, prevents brute-forcing).

Both calls append to `gates.jsonl` — including the rejected dimensions on commit — so post-hoc human review can detect skipped audits.

### `verify_links`

```jsonc
{
  "project_root": "/path/to/repo",
  "feature": "checkout-flow"
}
```

Parses each spec's `## Links` section (or `<!-- LINKS -->` block) and verifies that referenced files exist and contain a reciprocal back-link. Reports `missing`, `stale`, and `orphaned` categories. Read-only.

Folder resolution: per-call `link_dirs` argument > `<project_root>/.contractfirst/config.json` (`"link_dirs"` key) > built-in defaults. Monorepos that don't follow `docs/specs` / `docs/invariants` should set the config file once instead of overriding every call.

### `analyze_verify_failure`

```jsonc
{
  "project_root": "/path/to/repo",
  "verify_log_path": "/path/to/repo/.contractfirst/verify-20260511-103000.log",
  "failed_step": "test",
  "contract_paths": ["docs/invariants/payment.md"]
}
```

Classification is layered (strongest signal wins):

1. `failed_step == "test"` → always `contract_sensitive`.
2. Any suspected file in contract dirs (`specs/`, `invariants/`, `interfaces/`, `tests/`) or matching filename conventions (`*.spec.*`, `*_test.*`, `test_*`).
3. Multi-framework structured failure markers — pytest, unittest, Jest, Vitest, Mocha/Chai, RSpec, Minitest, Go test, Rust assert, NUnit, xUnit, ExUnit, node:assert.
4. `lint` / `format` steps default to `routine` unless 1–3 say otherwise.

For `contract_sensitive`, `h4_gate.patch_allowed` is `false` and no fix snippet appears anywhere — the human must approve a fix strategy first. For `routine` (lint, simple typo), `patch_allowed` is `true` and minimal fix options are returned. The result includes `classification_signals` so the human can audit why the tool classified the way it did.

### `track_manual_checks`

```jsonc
// declare
{
  "project_root": "/path/to/repo",
  "feature": "minigame-ui",
  "op": "declare",
  "checks": [
    {"id": "V1", "description": "ProximityPrompt 3x → only one UI", "required": true},
    {"id": "V2", "description": "close + reopen works"},
    {"id": "V3", "description": "perf check at 1080p", "required": false}
  ]
}

// confirm
{ "project_root": "...", "feature": "minigame-ui", "op": "confirm", "check_id": "V1", "note": "playtest 3 min" }

// hand off to another party (still counts as resolved)
{ "project_root": "...", "feature": "minigame-ui", "op": "handoff", "check_id": "V3", "note": "QA ticket #1234" }

// inspect
{ "project_root": "...", "feature": "minigame-ui", "op": "summary" }
```

Per-feature ledger persisted at `<project_root>/.contractfirst/manual-checks/<feature>.json`. `run_verify(feature=...)` consults this ledger to gate `overall: pass`. This is the primary verification surface for ui-heavy projects (visual layout, interaction feel, focus order, playtest) — things `verify.sh` cannot check.

## Run the tests

```bash
pip install -e ".[dev]"
pytest
```

64 tests across the seven tools, covering happy paths, classifier signals across frameworks, the manual-check interlock, evidence validation, and gate-log emission.

## Design notes

- **No hidden state.** Every tool call is independent. Pass everything via arguments.
- **No network.** Everything runs locally against the file system and subprocess.
- **Errors return structured results** (not exceptions), except for invalid input — those raise `ValueError`.
- **Gates that depend on AI-supplied inputs require evidence.** `score_ambiguity` will reject empty or under-length evidence quotes; the literal `"none"` token forces low scores. This is the cheapest mitigation against the AI inflating its own clarity scores to bypass the gate.
- The whole point of this server is to be **the thing the AI cannot lie about**. If a tool's result depended purely on the AI's own judgment, it would belong in the skill prompt, not here.

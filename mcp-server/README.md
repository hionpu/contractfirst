# lowtech-tdd-mcp

An MCP server that provides **deterministic, non-bypassable checkpoints** for the [`lowtech-tdd`](https://github.com/) workflow. The `lowtech-tdd` skill is a prompt — when context drifts, the model can ignore it. This server exposes four tools whose outputs are externally verifiable: if the AI claims tests passed, you can re-run the same tool on the same inputs and falsify the claim.

Scope is deliberately narrow: **four tools only**. File-write guards, contract-change workflows, plan gates, and human-zone tracking live elsewhere (OS permissions, Git, the skill prompt). This server only handles the parts the AI is most likely to fake or skip.

## The four tools

| Tool | Replaces this AI failure mode |
|------|-------------------------------|
| `run_verify` | "Tests passed" — when they didn't, or weren't actually run |
| `score_ambiguity` | "The spec is clear enough" — AI grading its own homework |
| `verify_links` | "Links are complete" — without actually checking files |
| `analyze_verify_failure` | Patching before understanding root cause |

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
claude mcp add lowtech-tdd-mcp -- python -m lowtech_tdd_mcp.server
```

**Codex CLI** (`~/.codex/config.toml`)

```toml
[mcp_servers.lowtech-tdd-mcp]
command = "python"
args = ["-m", "lowtech_tdd_mcp.server"]
```

Both clients launch the server over stdio.

## Example calls

### `run_verify`

```jsonc
{
  "project_root": "/path/to/repo",
  "scope": "full",
  "verify_script": "./verify.sh"
}
```

Runs `./verify.sh full` if the script exists; otherwise falls back to language-detected defaults (`npm run typecheck/test/lint/build` for Node, `mypy . / pytest / ruff check .` for Python). Full logs are written under `<project_root>/.lowtech-tdd/verify-<timestamp>.log`; the truncated tail (last 2000 chars per stream) is returned inline.

### `score_ambiguity`

```jsonc
{
  "goal_clarity": 0.9,
  "constraint_clarity": 0.7,
  "success_criteria_clarity": 0.8,
  "blocking_questions": [],
  "open_questions": ["Should we cache responses?"]
}
```

Weights are fixed at 0.40 / 0.30 / 0.30. `proceed: true` only when `ambiguity <= 0.20` and `blocking_questions` is empty. The returned `report_markdown` is the verbatim template the skill expects to print.

### `verify_links`

```jsonc
{
  "project_root": "/path/to/repo",
  "feature": "checkout-flow"
}
```

Parses each spec's `## Links` section (or `<!-- LINKS -->` block) and verifies that referenced files exist and contain a reciprocal back-link. Reports `missing`, `stale`, and `orphaned` categories. Read-only.

### `analyze_verify_failure`

```jsonc
{
  "project_root": "/path/to/repo",
  "verify_log_path": "/path/to/repo/.lowtech-tdd/verify-20260511-103000.log",
  "failed_step": "test",
  "contract_paths": ["docs/invariants/payment.md"]
}
```

Classifies the failure as `contract_sensitive` or `routine`. For `contract_sensitive`, `h4_gate.patch_allowed` is `false` and no fix snippet appears anywhere — the human must approve a fix strategy first. For `routine` (lint, simple typo), `patch_allowed` is `true` and minimal fix options are returned.

## Run the tests

```bash
pip install -e ".[dev]"
pytest
```

## Design notes

- **No hidden state.** Every tool call is independent. Pass everything via arguments.
- **No network.** Everything runs locally against the file system and subprocess.
- **Errors return structured results** (not exceptions), except for invalid input — those raise `ValueError`.
- The whole point of this server is to be **the thing the AI cannot lie about**. If a tool's result depended on the AI's own judgment, it would belong in the skill prompt, not here.

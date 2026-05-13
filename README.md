lowtech-tdd
===========

**Contract-enforced development harness for AI-assisted coding.**

Prevents AI from writing code before the contract is clear. Prevents fake "all tests passed" reports. Preserves human debugging and design skills.

Two components:

* **Skill** — behavior instructions loaded by Claude Code / Codex / Gemini CLI at session start
* **MCP server** — five deterministic verification tools the AI cannot lie about

> **New here?** Read [`OVERVIEW.md`](./OVERVIEW.md) for what this harness does, how it works, and how it compares to other AI-coding workflows (superpowers, plain CLAUDE.md rules, bare sessions). This README is install + reference.

* * *

One-liner Install
-----------------

    curl -fsSL https://raw.githubusercontent.com/hionpu/contractfirst/main/install.sh | bash

Installs both Skill and MCP server, and registers with whatever CLI tools are detected (Claude Code, Codex CLI, Gemini CLI).

### Options

    # Skill only (no MCP server)
    curl -fsSL .../install.sh | bash -s -- --skill-only
    
    # MCP only
    curl -fsSL .../install.sh | bash -s -- --mcp-only
    
    # Install into a specific project directory
    curl -fsSL .../install.sh | bash -s -- --target ./my-project

* * *

One-liner Uninstall
-------------------

    curl -fsSL https://raw.githubusercontent.com/hionpu/contractfirst/main/uninstall.sh | bash

Removes skill files, cleans up CLI config imports, deregisters the MCP server, and uninstalls the Python package. Verify logs (`.lowtech-tdd/`) are removed interactively.

### Options

    # Skill only
    curl -fsSL .../uninstall.sh | bash -s -- --skill-only
    
    # MCP only
    curl -fsSL .../uninstall.sh | bash -s -- --mcp-only
    
    # Target a specific project directory
    curl -fsSL .../uninstall.sh | bash -s -- --target ./my-project

### What uninstall does NOT touch

* `docs/specs/`, `docs/invariants/` — your contract files, not ours

* `verify.sh` — your project file

* Files locked with `chmod 444` — restore manually if needed:
  
      chmod 644 docs/specs/*.md docs/invariants/*.md
  
  

* * *

What Gets Installed
-------------------

### Skill (`~/.claude/` or `<project>/.claude/`)

    .claude/
    ├── SKILL.md                  ← loaded at session start
    └── references/
        ├── slicing.md                ← vertical slice guide
        ├── spec-template.md          ← spec document template
        ├── platforms.md              ← Roblox/Unity/Elixir/TS/Python tool mapping
        ├── test-onboarding.md        ← building test infra from zero
        ├── links.md                  ← Spec ↔ Invariant ↔ Interface ↔ Test rules
        ├── project-types.md          ← logic-heavy / ui-heavy / mixed guidance
        └── architecture-patterns.md  ← MVC / MVVM / ECS / Flux / Hexagonal invariants

### MCP Server (`~/.local/share/lowtech-tdd-mcp/`)

Five tools:

| Tool                     | What it does                                                                               |
| ------------------------ | ------------------------------------------------------------------------------------------ |
| `run_verify`             | Runs `verify.sh` and returns structured results. With `feature=...`, downgrades a green automatic run to `pending_manual` while manual checks remain. |
| `score_ambiguity`        | Computes ambiguity score from per-dimension scores **with required verbatim evidence quotes**. Blocks proceeding if > 0.20. |
| `verify_links`           | Parses contract files and checks Spec ↔ Invariant ↔ Interface ↔ Test link integrity. Honors `.lowtech-tdd/config.json`. |
| `analyze_verify_failure` | Produces root-cause hypotheses. Multi-framework structured detection (pytest/Jest/Go/RSpec/Rust/.NET). Blocks patch writing for contract-sensitive failures. |
| `track_manual_checks`    | Per-feature ledger of manual verification items. Consumed by `run_verify` to gate `overall: pass` for ui-heavy / mixed projects. |

All gate decisions append one JSON line to `.lowtech-tdd/gates.jsonl` so the history is auditable.

* * *

Manual Setup
------------

### Skill only

    git clone https://github.com/hionpu/contractfirst
    cp -r lowtech-tdd/skill/.claude /path/to/your/project/
    echo "@.claude/SKILL.md" >> /path/to/your/project/CLAUDE.md

### MCP server only

    pip install -e ./mcp-server
    
    # Claude Code
    claude mcp add lowtech-tdd --scope project -- python -m lowtech_tdd_mcp.server
    
    # Codex CLI — append to ~/.codex/config.toml:
    # [mcp_servers.lowtech-tdd]
    # command = "python"
    # args = ["-m", "lowtech_tdd_mcp.server"]
    
    # Gemini CLI — add to ~/.gemini/settings.json:
    # { "mcpServers": { "lowtech-tdd": { "command": "python", "args": ["-m", "lowtech_tdd_mcp.server"] } } }

* * *

After Install
-------------

    # Lock contract files (OS-level enforcement)
    chmod 444 docs/specs/*.md docs/invariants/*.md
    
    # Add a verify.sh to your project root
    cat > verify.sh << 'EOF'
    #!/bin/bash
    set -e
    echo "=== Typecheck ===" && <your typecheck command>
    echo "=== Test ===" && <your test command>
    echo "=== Lint ===" && <your lint command>
    echo "=== All checks passed ==="
    EOF
    chmod +x verify.sh

Then open Claude Code (or Codex / Gemini CLI) in your project directory. The harness is active.

* * *

How It Works
------------

    User: "implement login feature"
             ↓
    Claude Code reads SKILL.md at session start
             ↓
    Scale Triage (Q0–Q3) → Medium
             ↓
    Clarification Gate → calls score_ambiguity MCP tool
      ambiguity: 0.43 > 0.20 → proceed: false
             ↓
    Claude asks clarifying questions, waits
             ↓
    [user answers] → score_ambiguity → 0.18 ≤ 0.20 → proceed: true
             ↓
    Spec + Interface agreed by human
             ↓
    Claude implements (contract files are chmod 444 — physically blocked)
             ↓
    Claude calls run_verify MCP tool → real results, cannot fake
             ↓
    If fail: analyze_verify_failure → root cause only, no patch
    Human approves fix strategy → Claude writes patch → run_verify again
             ↓
    Medium+: verify_links → checks cross-references
             ↓
    Done

* * *

Repository Structure
--------------------

    lowtech-tdd/
    ├── install.sh                  ← one-liner installer
    ├── uninstall.sh                ← one-liner uninstaller
    ├── README.md
    ├── skill/
    │   ├── SKILL.md                ← main skill file
    │   └── references/
    │       ├── slicing.md
    │       ├── spec-template.md
    │       ├── platforms.md
    │       ├── test-onboarding.md
    │       ├── links.md
    │       ├── project-types.md
    │       └── architecture-patterns.md
    └── mcp-server/
        ├── pyproject.toml
        ├── README.md
        └── src/
            └── lowtech_tdd_mcp/
                ├── server.py
                ├── verify.py
                ├── ambiguity.py
                ├── links.py
                ├── failure.py
                ├── manual_checks.py
                └── gatelog.py

* * *

Supported CLI Tools
-------------------

| Tool        | Skill                                          | MCP                             |
| ----------- | ---------------------------------------------- | ------------------------------- |
| Claude Code | ✅ via `CLAUDE.md` (`@`-import)                 | ✅ via `claude mcp add`          |
| Codex CLI   | ✅ via `AGENTS.md` (plain-text directive — no `@`-import support) | ✅ via `~/.codex/config.toml`    |
| Gemini CLI  | ✅ via `GEMINI.md` (`@`-import)                 | ✅ via `~/.gemini/settings.json` |

* * *

License
-------

Apache-2.0

contractfirst
===========

**Contract-enforced development harness for AI-assisted coding.**

Prevents AI from writing code before the contract is clear. Prevents fake "all tests passed" reports. Preserves human debugging and design skills.

Two components:

* **Skill** — behavior instructions loaded by Claude Code / Codex / Gemini CLI / Pi / opencode at session start
* **MCP server** — seven deterministic verification tools whose outputs are saved on disk and re-runnable, so AI claims about them are checkable

> **New here?** Read [`OVERVIEW.md`](./OVERVIEW.md) for what this harness does, how it works, and how it compares to other AI-coding workflows (superpowers, plain CLAUDE.md rules, bare sessions). This README is install + reference.

* * *

One-liner Install
-----------------

    curl -fsSL https://raw.githubusercontent.com/hionpu/contractfirst/main/install.sh | bash

Installs both Skill and MCP server, and registers with whatever CLI tools are detected (Claude Code, Codex CLI, Gemini CLI, Pi, opencode).

### Options

    # Skill only (no MCP server)
    curl -fsSL .../install.sh | bash -s -- --skill-only
    
    # MCP only
    curl -fsSL .../install.sh | bash -s -- --mcp-only
    
    # Install into a specific project directory
    curl -fsSL .../install.sh | bash -s -- --target ./my-project

    # Install for specific CLI tools only (comma-separated)
    curl -fsSL .../install.sh | bash -s -- --cli claude
    curl -fsSL .../install.sh | bash -s -- --cli claude,codex
    curl -fsSL .../install.sh | bash -s -- --cli claude,codex,gemini,pi,opencode

Default (no `--cli`): auto-detects installed CLIs from PATH.

| `--cli` value | Skill file | MCP config |
|---|---|---|
| `claude` | `CLAUDE.md` (`@`-import) | `claude mcp add` (project-scoped) |
| `codex` | `AGENTS.md` (plain-text directive) | `~/.codex/config.toml` |
| `gemini` | `GEMINI.md` (`@`-import) | `~/.gemini/settings.json` |
| `pi` | `~/.pi/agent/skills/contractfirst` + `AGENTS.md` | `~/.pi/agent/mcp.json` ([pi-mcp-adapter](https://github.com/nicobailon/pi-mcp-adapter)) |
| `opencode` | `AGENTS.md` (plain-text directive) | `~/.config/opencode/opencode.json` |

* * *

One-liner Update
----------------

    curl -fsSL https://raw.githubusercontent.com/hionpu/contractfirst/main/update.sh | bash

Pulls latest from GitHub, reinstalls the Python package, and overwrites skill files. Does not touch `CLAUDE.md`, MCP registration, or your project's contract files.

### Options

    # Skill only
    curl -fsSL .../update.sh | bash -s -- --skill-only
    
    # MCP only
    curl -fsSL .../update.sh | bash -s -- --mcp-only
    
    # Update skill in a specific project directory
    curl -fsSL .../update.sh | bash -s -- --target ./my-project

Or run directly from the local install (no curl needed):

    bash ~/.local/share/contractfirst/update.sh

* * *

One-liner Uninstall
-------------------

    curl -fsSL https://raw.githubusercontent.com/hionpu/contractfirst/main/uninstall.sh | bash

Removes skill files, cleans up CLI config imports, deregisters the MCP server, and uninstalls the Python package. Verify logs (`.contractfirst/`) are removed interactively.

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

### Skill

Project copy (`<project>/.claude/skills/contractfirst/`):

    .claude/
    └── skills/
        └── contractfirst/
            ├── SKILL.md                  ← loaded at session start
            └── references/
                ├── slicing.md                ← vertical slice guide
                ├── spec-template.md          ← spec document template
                ├── platforms.md              ← Roblox/Unity/Elixir/TS/Python tool mapping
                ├── test-onboarding.md        ← building test infra from zero
                ├── links.md                  ← Spec ↔ Invariant ↔ Interface ↔ Test rules
                ├── project-types.md          ← logic-heavy / ui-heavy / mixed guidance
                └── architecture-patterns.md  ← MVC / MVVM / ECS / Flux / Hexagonal invariants

Pi native copy (`--cli pi`): `~/.pi/agent/skills/lowtech-tdd/`. Re-running install overwrites `SKILL.md` and references there, so legacy Pi installs get updated. The Pi copy keeps `name: lowtech-tdd` so it matches its directory and existing `/skill:lowtech-tdd` usage.

### MCP Server (`~/.local/share/contractfirst/`)

Seven tools:

| Tool                       | What it does                                                                                                       |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `run_verify`               | Runs `verify.sh` and returns structured results. With `feature=...`, downgrades a green automatic run to `pending_manual` while manual checks remain. |
| `score_ambiguity`          | Single-call ambiguity gate. Requires verbatim evidence quotes; `none`-evidence forces score ≤ 0.30. Returns `proceed: false` if > 0.20. |
| `draft_ambiguity_score`    | Step 1 of audited two-step gate. Stages Agent A's scores+evidence, returns an auditor prompt and one-time `audit_token` for sub-agent dispatch. |
| `commit_ambiguity_audit`   | Step 2 of audited two-step gate. Parses sub-agent verdict; forces rejected dimensions to 0.0; returns final `proceed`. |
| `verify_links`             | Parses contract files and checks Spec ↔ Invariant ↔ Interface ↔ Test link integrity. Honors `.contractfirst/config.json`. |
| `analyze_verify_failure`   | Produces root-cause hypotheses. Multi-framework structured detection (pytest/Jest/Go/RSpec/Rust/.NET). Blocks patch writing for contract-sensitive failures. |
| `track_manual_checks`      | Per-feature ledger of manual verification items. Consumed by `run_verify` to gate `overall: pass` for ui-heavy / mixed projects. |

All gate decisions append one JSON line to `.contractfirst/gates.jsonl` so the history is auditable.

* * *

Manual Setup
------------

### Skill only

    git clone https://github.com/hionpu/contractfirst
    mkdir -p /path/to/your/project/.claude/skills/contractfirst
    cp -r skill/SKILL.md skill/references /path/to/your/project/.claude/skills/contractfirst/
    echo "@.claude/skills/contractfirst/SKILL.md" >> /path/to/your/project/CLAUDE.md

### MCP server only

    pip install -e ./mcp-server
    
    # Claude Code
    claude mcp add contractfirst --scope project -- python -m contractfirst.server
    
    # Codex CLI — append to ~/.codex/config.toml:
    # [mcp_servers.contractfirst]
    # command = "python"
    # args = ["-m", "contractfirst.server"]
    
    # Gemini CLI — add to ~/.gemini/settings.json:
    # { "mcpServers": { "contractfirst": { "command": "python", "args": ["-m", "contractfirst.server"] } } }
    
    # Pi MCP adapter — add to ~/.pi/agent/mcp.json:
    # { "mcpServers": { "contractfirst": { "command": "python", "args": ["-m", "contractfirst.server"], "lifecycle": "lazy", "idleTimeout": 10 } } }

* * *

After Install
-------------

    # Lock contract files (OS-level enforcement — POSIX / WSL / macOS / Linux)
    chmod 444 docs/specs/*.md docs/invariants/*.md
    
    # Windows-native equivalent (PowerShell): use the read-only attribute,
    # or NTFS ACLs (`icacls`) for stronger enforcement. See OVERVIEW.md.
    
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

    contractfirst/
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
            └── contractfirst/
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

| Tool        | `--cli` value | Skill                                          | MCP                             |
| ----------- | ------------- | ---------------------------------------------- | ------------------------------- |
| Claude Code | `claude`      | ✅ via `CLAUDE.md` (`@`-import)                 | ✅ via `claude mcp add`          |
| Codex CLI   | `codex`       | ✅ via `AGENTS.md` (plain-text directive)       | ✅ via `~/.codex/config.toml`    |
| Gemini CLI  | `gemini`      | ✅ via `GEMINI.md` (`@`-import)                 | ✅ via `~/.gemini/settings.json` |
| Pi          | `pi`          | ✅ via native Pi skill dir + `AGENTS.md`        | ✅ via Pi MCP adapter (`~/.pi/agent/mcp.json`) |
| opencode    | `opencode`    | ✅ via `AGENTS.md` (plain-text directive)       | ✅ via `~/.config/opencode/opencode.json` |

* * *

License
-------

Apache-2.0

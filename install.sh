#!/bin/bash
# contractfirst installer
# Usage: curl -fsSL https://raw.githubusercontent.com/hionpu/contractfirst/main/install.sh | bash
# Options:
#   --skill-only                    Install skill files only, skip MCP server
#   --mcp-only                      Install MCP server only, skip skill files
#   --target ./my-project           Install skill into a specific project directory
#   --cli claude,codex,...          Install for specific CLI tools only
#                                   Valid: claude, codex, gemini, pi, opencode
#                                   Default: auto-detect from PATH

set -e

SCRIPT_VERSION="2026-05-19 13:37"

REPO="https://github.com/hionpu/contractfirst"
RAW="https://raw.githubusercontent.com/hionpu/contractfirst/main"
SKILL_ONLY=false
MCP_ONLY=false
TARGET="."
CLI_LIST=""   # empty = auto-detect from PATH
REFS="slicing spec-template platforms test-onboarding links project-types architecture-patterns"

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --skill-only) SKILL_ONLY=true; shift ;;
        --mcp-only)   MCP_ONLY=true;  shift ;;
        --target)     TARGET="$2";    shift 2 ;;
        --cli)        CLI_LIST="$2";  shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo "╔══════════════════════════════════════╗"
echo "║      contractfirst Setup       ║"
echo "╚══════════════════════════════════════╝"
echo "  script version: $SCRIPT_VERSION"
echo ""

has() { command -v "$1" &>/dev/null; }
fetch() {
    if has curl; then curl -fsSL "$1"
    else wget -qO- "$1"; fi
}

# Validate --cli list
_VALID_CLIS="claude codex gemini pi opencode"
if [[ -n "$CLI_LIST" ]]; then
    for _name in $(echo "$CLI_LIST" | tr ',' ' '); do
        _ok=false
        for _v in $_VALID_CLIS; do [[ "$_name" == "$_v" ]] && _ok=true && break; done
        if ! $_ok; then
            echo "Error: unknown CLI tool '$_name'"
            echo "Valid values: $_VALID_CLIS"
            exit 1
        fi
    done
    echo "Installing for: $(echo "$CLI_LIST" | tr ',' ' ')"
else
    echo "Auto-detecting installed CLI tools..."
fi
echo ""

# Check if a CLI tool is enabled for this install.
# With --cli: explicit list. Without: detect binary in PATH.
cli_enabled() {
    local name="$1"
    if [[ -z "$CLI_LIST" ]]; then
        has "$name"
    else
        echo "$CLI_LIST" | tr ',' '\n' | grep -qx "$name"
    fi
}

# python3 required for MCP server install and Gemini/Pi/opencode config edits
if ! has python3 && ! $SKILL_ONLY; then
    echo "Error: python3 is required but not found in PATH"
    echo "Install Python 3.11+ and re-run."
    exit 1
fi

# ── Install Skill ──────────────────────────────────────────────
install_skill_files() {
    local dir="$1"
    local skill_name="${2:-contractfirst}"
    mkdir -p "$dir/references"
    fetch "$RAW/skill/SKILL.md" > "$dir/SKILL.md"
    if [[ "$skill_name" != "contractfirst" ]]; then
        python3 - "$dir/SKILL.md" "$skill_name" <<'PYEOF'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
name = sys.argv[2]
text = path.read_text(encoding="utf-8")
text = text.replace("name: contractfirst", f"name: {name}", 1)
path.write_text(text, encoding="utf-8")
PYEOF
    fi
    for ref in $REFS; do
        fetch "$RAW/skill/references/$ref.md" > "$dir/references/$ref.md"
    done
}

install_skill() {
    echo "→ Installing skill files..."

    SKILL_DIR="$TARGET/.claude/skills/contractfirst"
    install_skill_files "$SKILL_DIR"
    echo "  ✓ Skill files → $SKILL_DIR/"

    # ── Pi native skill store
    if cli_enabled pi; then
        PI_SKILL_DIR="${PI_SKILL_DIR:-$HOME/.pi/agent/skills/contractfirst}"
        install_skill_files "$PI_SKILL_DIR"
        echo "  ✓ Pi native skill → $PI_SKILL_DIR/"
    fi

    # ── Claude Code: CLAUDE.md with @-import
    if cli_enabled claude; then
        _md=""
        for _c in "$TARGET/CLAUDE.md" "$TARGET/claude.md"; do
            [[ -f "$_c" ]] && _md="$_c" && break
        done
        [[ -z "$_md" ]] && _md="$TARGET/CLAUDE.md" && touch "$_md"
        if ! grep -q "contractfirst" "$_md" 2>/dev/null; then
            printf '\n# contractfirst\n@.claude/skills/contractfirst/SKILL.md\n' >> "$_md"
        fi
        echo "  ✓ Imported in $_md (Claude Code)"
    fi

    # ── Codex / Pi / opencode: AGENTS.md with plain-text directive
    if cli_enabled codex || cli_enabled pi || cli_enabled opencode; then
        _md=""
        for _c in "$TARGET/AGENTS.md" "$TARGET/agents.md"; do
            [[ -f "$_c" ]] && _md="$_c" && break
        done
        [[ -z "$_md" ]] && _md="$TARGET/AGENTS.md" && touch "$_md"
        if ! grep -q "contractfirst\|contractfirst/SKILL\.md" "$_md" 2>/dev/null; then
            printf '\n# contractfirst\nThis project uses the contractfirst harness.\nRead .claude/skills/contractfirst/SKILL.md and the .claude/skills/contractfirst/references/ directory before any code change.\n' >> "$_md"
        fi
        _who=""
        cli_enabled codex    && _who="${_who}Codex "
        cli_enabled pi       && _who="${_who}Pi "
        cli_enabled opencode && _who="${_who}opencode"
        echo "  ✓ Imported in $_md (${_who% })"
        if cli_enabled pi; then
            echo "  ℹ Pi: native skill installed; AGENTS.md directive kept for project context"
        fi
    fi

    # ── Gemini CLI: GEMINI.md with @-import
    if cli_enabled gemini; then
        _md=""
        for _c in "$TARGET/GEMINI.md" "$TARGET/gemini.md"; do
            [[ -f "$_c" ]] && _md="$_c" && break
        done
        [[ -z "$_md" ]] && _md="$TARGET/GEMINI.md" && touch "$_md"
        if ! grep -q "contractfirst\|contractfirst/SKILL\.md" "$_md" 2>/dev/null; then
            printf '\n# contractfirst\n@.claude/skills/contractfirst/SKILL.md\n' >> "$_md"
        fi
        echo "  ✓ Imported in $_md (Gemini CLI)"
    fi
}

# ── Install MCP ────────────────────────────────────────────────
install_mcp() {
    echo "→ Installing MCP server..."

    MCP_DIR="$HOME/.local/share/contractfirst"

    # Clone or update local install
    if [[ -d "$MCP_DIR/.git" ]]; then
        echo "  Updating existing install..."
        git -C "$MCP_DIR" pull --quiet
    else
        git clone --quiet "$REPO" "$MCP_DIR"
    fi

    # Install Python package — uv first, pip fallback
    _pkg_installed=false
    if has uv; then
        if uv pip install -e "$MCP_DIR/mcp-server" --system --quiet 2>/dev/null; then
            _pkg_installed=true
        fi
    fi
    if ! $_pkg_installed; then
        if has pip3; then
            pip3 install -e "$MCP_DIR/mcp-server" --quiet --break-system-packages 2>/dev/null \
                || pip3 install -e "$MCP_DIR/mcp-server" --quiet
        elif has pip; then
            pip install -e "$MCP_DIR/mcp-server" --quiet
        elif has python3; then
            python3 -m pip install -e "$MCP_DIR/mcp-server" --quiet --break-system-packages 2>/dev/null \
                || python3 -m pip install -e "$MCP_DIR/mcp-server" --quiet
        else
            echo "  Error: no pip/uv found — install Python 3.11+ and re-run"
            exit 1
        fi
    fi
    echo "  ✓ Package installed → $MCP_DIR"

    # ── Claude Code
    if cli_enabled claude; then
        if has claude; then
            claude mcp add contractfirst \
                --scope project \
                -- python -m contractfirst.server 2>/dev/null \
                && echo "  ✓ Registered with Claude Code" \
                || echo "  ⚠ Registration failed — run: claude mcp add contractfirst --scope project -- python -m contractfirst.server"
        else
            echo "  ⚠ claude binary not found — register manually:"
            echo "    claude mcp add contractfirst --scope project -- python -m contractfirst.server"
        fi
    fi

    # ── Codex CLI (~/.codex/config.toml)
    if cli_enabled codex; then
        mkdir -p "$HOME/.codex"
        CODEX_CFG="$HOME/.codex/config.toml"
        [[ ! -f "$CODEX_CFG" ]] && touch "$CODEX_CFG"
        if ! grep -q "contractfirst" "$CODEX_CFG" 2>/dev/null; then
            cat >> "$CODEX_CFG" << 'EOF'

[mcp_servers.contractfirst]
command = "python"
args = ["-m", "contractfirst.server"]
EOF
            echo "  ✓ Registered with Codex CLI (~/.codex/config.toml)"
        else
            echo "  ✓ Already registered with Codex CLI"
        fi
    fi

    # ── Gemini CLI (~/.gemini/settings.json)
    # Use Python Path.home() — avoids Git Bash /c/Users/... path issue on Windows
    if cli_enabled gemini; then
        python3 - <<'PYEOF'
import json, pathlib
cfg_path = pathlib.Path.home() / ".gemini" / "settings.json"
cfg_path.parent.mkdir(parents=True, exist_ok=True)
try:
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
except json.JSONDecodeError:
    cfg = {}
if "contractfirst" not in cfg.get("mcpServers", {}):
    cfg.setdefault("mcpServers", {})["contractfirst"] = {
        "command": "python",
        "args": ["-m", "contractfirst.server"]
    }
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print("  ✓ Registered with Gemini CLI (~/.gemini/settings.json)")
else:
    print("  ✓ Already registered with Gemini CLI")
PYEOF
    fi

    # ── Pi MCP adapter (~/.pi/agent/mcp.json)
    if cli_enabled pi; then
        python3 - <<'PYEOF'
import json, pathlib
cfg_path = pathlib.Path.home() / ".pi" / "agent" / "mcp.json"
cfg_path.parent.mkdir(parents=True, exist_ok=True)
try:
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
except json.JSONDecodeError:
    cfg = {}
servers = cfg.setdefault("mcpServers", {})
entry = {
    "command": "python",
    "args": ["-m", "contractfirst.server"],
    "lifecycle": "lazy",
    "idleTimeout": 10,
}
changed = False
if servers.get("contractfirst") != entry:
    servers["contractfirst"] = entry
    changed = True
# Remove legacy lowtech-tdd key if present (rename migration)
if "lowtech-tdd" in servers:
    del servers["lowtech-tdd"]
    changed = True
if changed:
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(f"  ✓ Registered with Pi MCP adapter ({cfg_path})")
else:
    print("  ✓ Already registered with Pi MCP adapter")
PYEOF
    fi

    # ── opencode (~/.config/opencode/opencode.json)
    if cli_enabled opencode; then
        python3 - <<'PYEOF'
import json, pathlib
cfg_path = pathlib.Path.home() / ".config" / "opencode" / "opencode.json"
cfg_path.parent.mkdir(parents=True, exist_ok=True)
try:
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
except json.JSONDecodeError:
    cfg = {}
if "contractfirst" not in cfg.get("mcp", {}):
    cfg.setdefault("mcp", {})["contractfirst"] = {
        "type": "local",
        "command": ["python", "-m", "contractfirst.server"]
    }
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print("  ✓ Registered with opencode (~/.config/opencode/opencode.json)")
else:
    print("  ✓ Already registered with opencode")
PYEOF
    fi
}

# ── Run ────────────────────────────────────────────────────────
if $MCP_ONLY; then
    install_mcp
elif $SKILL_ONLY; then
    install_skill
else
    install_skill
    install_mcp
fi

echo ""
echo "╔══════════════════════════════════════╗"
echo "║              Done!                  ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "  1. Lock contract files:  chmod 444 docs/specs/*.md docs/invariants/*.md"
echo "  2. Add verify.sh to your project root"
echo "  3. Open your CLI tool in this directory — the harness is active"
echo ""
echo "Docs: $REPO"

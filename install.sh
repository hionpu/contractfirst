#!/bin/bash
# lowtech-tdd installer
# Usage: curl -fsSL https://raw.githubusercontent.com/hionpu/contractfirst/main/install.sh | bash
# Or with options:
#   bash install.sh --skill-only
#   bash install.sh --mcp-only
#   bash install.sh --target ./my-project

set -e

REPO="https://github.com/hionpu/contractfirst"
RAW="https://raw.githubusercontent.com/hionpu/contractfirst/main"
SKILL_ONLY=false
MCP_ONLY=false
TARGET="."

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --skill-only) SKILL_ONLY=true; shift ;;
        --mcp-only)   MCP_ONLY=true;  shift ;;
        --target)     TARGET="$2";    shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo "╔══════════════════════════════════════╗"
echo "║   Low-Tech Dept TDD Harness Setup   ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── Detect tools ──────────────────────────────────────────────
has() { command -v "$1" &>/dev/null; }

if ! has curl && ! has wget; then
    echo "Error: curl or wget required"; exit 1
fi

# python3 is required for the MCP server install and Codex/Gemini config edits.
# Fail loudly up-front so we don't leave a partial install.
if ! has python3 && ! $SKILL_ONLY; then
    echo "Error: python3 is required but not found in PATH"
    echo "Install Python 3.11+ and re-run."
    exit 1
fi

fetch() {
    if has curl; then curl -fsSL "$1"
    else wget -qO- "$1"; fi
}

# ── Install Skill ──────────────────────────────────────────────
install_skill() {
    echo "→ Installing skill..."
    mkdir -p "$TARGET/.claude/references"

    fetch "$RAW/skill/SKILL.md" > "$TARGET/.claude/SKILL.md"

    for ref in slicing spec-template platforms test-onboarding links project-types architecture-patterns; do
        fetch "$RAW/skill/references/$ref.md" > "$TARGET/.claude/references/$ref.md"
    done

    # Detect CLAUDE.md / claude.md and append skill import if not already present
    CLAUDE_MD=""
    for candidate in "$TARGET/CLAUDE.md" "$TARGET/claude.md"; do
        if [[ -f "$candidate" ]]; then
            CLAUDE_MD="$candidate"; break
        fi
    done

    if [[ -z "$CLAUDE_MD" ]]; then
        CLAUDE_MD="$TARGET/CLAUDE.md"
        touch "$CLAUDE_MD"
    fi

    if ! grep -q "lowtech-tdd" "$CLAUDE_MD" 2>/dev/null; then
        echo "" >> "$CLAUDE_MD"
        echo "# Low-Tech Dept TDD Harness" >> "$CLAUDE_MD"
        echo "@.claude/SKILL.md" >> "$CLAUDE_MD"
    fi

    echo "  ✓ Skill installed → $TARGET/.claude/SKILL.md"
    echo "  ✓ References installed → $TARGET/.claude/references/"
    echo "  ✓ Imported in $CLAUDE_MD"

    # ── Codex CLI: AGENTS.md (no @-import support — write a plain-text directive
    # that Codex's agent will read literally from the concatenated AGENTS.md context)
    if has codex; then
        AGENTS_MD=""
        for candidate in "$TARGET/AGENTS.md" "$TARGET/agents.md"; do
            [[ -f "$candidate" ]] && AGENTS_MD="$candidate" && break
        done
        [[ -z "$AGENTS_MD" ]] && AGENTS_MD="$TARGET/AGENTS.md" && touch "$AGENTS_MD"
        if ! grep -q "lowtech-tdd\|SKILL\.md" "$AGENTS_MD" 2>/dev/null; then
            echo "" >> "$AGENTS_MD"
            echo "# Low-Tech Dept TDD Harness" >> "$AGENTS_MD"
            echo "This project uses the Low-Tech Dept TDD harness." >> "$AGENTS_MD"
            echo "Read .claude/SKILL.md and the .claude/references/ directory before any code change." >> "$AGENTS_MD"
        fi
        echo "  ✓ Imported in $AGENTS_MD"
    fi

    # ── Gemini CLI: GEMINI.md (supports @-import directive)
    if has gemini; then
        GEMINI_MD=""
        for candidate in "$TARGET/GEMINI.md" "$TARGET/gemini.md"; do
            [[ -f "$candidate" ]] && GEMINI_MD="$candidate" && break
        done
        [[ -z "$GEMINI_MD" ]] && GEMINI_MD="$TARGET/GEMINI.md" && touch "$GEMINI_MD"
        if ! grep -q "lowtech-tdd\|SKILL\.md" "$GEMINI_MD" 2>/dev/null; then
            echo "" >> "$GEMINI_MD"
            echo "# Low-Tech Dept TDD Harness" >> "$GEMINI_MD"
            echo "@.claude/SKILL.md" >> "$GEMINI_MD"
        fi
        echo "  ✓ Imported in $GEMINI_MD"
    fi
}

# ── Install MCP ────────────────────────────────────────────────
install_mcp() {
    echo "→ Installing MCP server..."

    MCP_DIR="$HOME/.local/share/lowtech-tdd-mcp"

    # Clone or update
    if [[ -d "$MCP_DIR/.git" ]]; then
        echo "  Updating existing install..."
        git -C "$MCP_DIR" pull --quiet
    else
        git clone --quiet "$REPO" "$MCP_DIR"
    fi

    # Install Python package
    if has uv; then
        uv pip install -e "$MCP_DIR/mcp-server" --quiet
    elif has pip3; then
        pip3 install -e "$MCP_DIR/mcp-server" --quiet --break-system-packages 2>/dev/null \
            || pip3 install -e "$MCP_DIR/mcp-server" --quiet
    elif has pip; then
        pip install -e "$MCP_DIR/mcp-server" --quiet
    else
        echo "  Error: pip or uv required for MCP server install"
        exit 1
    fi

    echo "  ✓ MCP server installed → $MCP_DIR"

    # Register with Claude Code
    # Correct syntax: claude mcp add <name> [--scope <scope>] -- <command> [args...]
    if has claude; then
        claude mcp add lowtech-tdd \
            --scope project \
            -- python -m lowtech_tdd_mcp.server 2>/dev/null \
            && echo "  ✓ Registered with Claude Code" \
            || echo "  ⚠ Claude Code registration failed — run manually: claude mcp add lowtech-tdd --scope project -- python -m lowtech_tdd_mcp.server"
    else
        echo "  ⚠ Claude Code not found — skipping registration"
    fi

    # Register with Codex CLI (config.toml, not config.json)
    if has codex; then
        CODEX_CFG="$HOME/.codex/config.toml"
        if [[ -f "$CODEX_CFG" ]]; then
            if ! grep -q "lowtech-tdd" "$CODEX_CFG"; then
                cat >> "$CODEX_CFG" << 'EOF'

[mcp_servers.lowtech-tdd]
command = "python"
args = ["-m", "lowtech_tdd_mcp.server"]
EOF
                echo "  ✓ Registered with Codex CLI"
            else
                echo "  ✓ Already registered with Codex CLI"
            fi
        else
            echo "  ⚠ Codex config not found at $CODEX_CFG — skipping"
        fi
    fi

    # Register with Gemini CLI
    if has gemini; then
        GEMINI_CFG="$HOME/.gemini/settings.json"
        mkdir -p "$(dirname "$GEMINI_CFG")"
        if [[ ! -f "$GEMINI_CFG" ]]; then
            echo '{}' > "$GEMINI_CFG"
        fi
        if ! grep -q "lowtech-tdd" "$GEMINI_CFG"; then
            python3 - <<EOF
import json
cfg = json.load(open("$GEMINI_CFG"))
cfg.setdefault("mcpServers", {})["lowtech-tdd"] = {
    "command": "python",
    "args": ["-m", "lowtech_tdd_mcp.server"]
}
json.dump(cfg, open("$GEMINI_CFG", "w"), indent=2)
print("  ✓ Registered with Gemini CLI")
EOF
        else
            echo "  ✓ Already registered with Gemini CLI"
        fi
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
echo "  3. Start Claude Code in this directory — the harness is active"
echo ""
echo "Docs: $REPO"

#!/bin/bash
# lowtech-tdd uninstaller
# Usage: curl -fsSL https://raw.githubusercontent.com/hionpu/contractfirst/main/uninstall.sh | bash
# Or with options:
#   bash uninstall.sh --skill-only
#   bash uninstall.sh --mcp-only
#   bash uninstall.sh --target ./my-project

set -e

SKILL_ONLY=false
MCP_ONLY=false
TARGET="."

while [[ $# -gt 0 ]]; do
    case $1 in
        --skill-only) SKILL_ONLY=true; shift ;;
        --mcp-only)   MCP_ONLY=true;  shift ;;
        --target)     TARGET="$2";    shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo "╔══════════════════════════════════════╗"
echo "║  Low-Tech Dept TDD Harness Removal  ║"
echo "╚══════════════════════════════════════╝"
echo ""

has() { command -v "$1" &>/dev/null; }

# python3 is needed for Gemini settings.json edit; fail fast on MCP-side uninstall.
if ! has python3 && ! $SKILL_ONLY; then
    echo "Error: python3 is required but not found in PATH"
    echo "Install Python 3.11+ and re-run."
    exit 1
fi

# ── Uninstall Skill ────────────────────────────────────────────
uninstall_skill() {
    echo "→ Removing skill..."

    # Remove .claude dir if it only contains lowtech-tdd files
    if [[ -d "$TARGET/.claude" ]]; then
        rm -f "$TARGET/.claude/SKILL.md"
        rm -rf "$TARGET/.claude/references"
        # Remove dir only if now empty
        rmdir "$TARGET/.claude" 2>/dev/null && echo "  ✓ Removed $TARGET/.claude/" \
            || echo "  ✓ Removed skill files (.claude/ kept — other files remain)"
    else
        echo "  ✓ No skill files found"
    fi

    # Remove lowtech-tdd skill block from CLAUDE.md / AGENTS.md / GEMINI.md.
    # CLAUDE.md and GEMINI.md use the @.claude/SKILL.md import line.
    # AGENTS.md (Codex) uses a plain-text directive — strip those lines too.
    for cfg in "$TARGET/CLAUDE.md" "$TARGET/claude.md" \
               "$TARGET/AGENTS.md" "$TARGET/agents.md" \
               "$TARGET/GEMINI.md" "$TARGET/gemini.md"; do
        if [[ -f "$cfg" ]] && grep -q "lowtech-tdd\|SKILL\.md" "$cfg" 2>/dev/null; then
            sed -i.bak \
                -e '/# Low-Tech Dept TDD Harness/d' \
                -e '/@\.claude\/SKILL\.md/d' \
                -e '/This project uses the Low-Tech Dept TDD harness\./d' \
                -e '/Read \.claude\/SKILL\.md and the \.claude\/references\/ directory before any code change\./d' \
                "$cfg"
            rm -f "$cfg.bak"
            echo "  ✓ Cleaned $cfg"
        fi
    done
}

# ── Uninstall MCP ──────────────────────────────────────────────
uninstall_mcp() {
    echo "→ Removing MCP server..."

    MCP_DIR="$HOME/.local/share/lowtech-tdd-mcp"

    # Deregister from Claude Code
    if command -v claude &>/dev/null; then
        claude mcp remove lowtech-tdd 2>/dev/null \
            && echo "  ✓ Deregistered from Claude Code" \
            || echo "  ✓ Not registered with Claude Code (skipping)"
    fi

    # Deregister from Codex CLI (config.toml, not config.json)
    CODEX_CFG="$HOME/.codex/config.toml"
    if [[ -f "$CODEX_CFG" ]] && grep -q "lowtech-tdd" "$CODEX_CFG"; then
        # Remove the [mcp_servers.lowtech-tdd] block: header + the two key lines that follow.
        sed -i.bak '/^\[mcp_servers\.lowtech-tdd\]/,/^args/d' "$CODEX_CFG"
        rm -f "$CODEX_CFG.bak"
        echo "  ✓ Deregistered from Codex CLI"
    fi

    # Deregister from Gemini CLI
    GEMINI_CFG="$HOME/.gemini/settings.json"
    if [[ -f "$GEMINI_CFG" ]] && grep -q "lowtech-tdd" "$GEMINI_CFG"; then
        python3 - <<EOF
import json
cfg = json.load(open("$GEMINI_CFG"))
cfg.get("mcpServers", {}).pop("lowtech-tdd", None)
json.dump(cfg, open("$GEMINI_CFG", "w"), indent=2)
print("  ✓ Deregistered from Gemini CLI")
EOF
    fi

    # Uninstall Python package
    if python3 -c "import lowtech_tdd_mcp" &>/dev/null; then
        if command -v uv &>/dev/null; then
            uv pip uninstall lowtech-tdd-mcp --quiet 2>/dev/null || true
        else
            pip3 uninstall lowtech-tdd-mcp -y --quiet 2>/dev/null \
                || pip uninstall lowtech-tdd-mcp -y --quiet 2>/dev/null \
                || true
        fi
        echo "  ✓ Python package uninstalled"
    fi

    # Remove server files
    if [[ -d "$MCP_DIR" ]]; then
        rm -rf "$MCP_DIR"
        echo "  ✓ Removed $MCP_DIR"
    else
        echo "  ✓ No server files found"
    fi

    # Remove verify logs if present.
    # When run via curl | bash, stdin is the script — read from /dev/tty if interactive,
    # otherwise default to keeping the logs so we don't accidentally delete user data.
    if [[ -d "$TARGET/.lowtech-tdd" ]]; then
        if [[ -t 0 ]]; then
            read -rp "  Remove verify logs at $TARGET/.lowtech-tdd/? [y/N] " yn < /dev/tty
        else
            yn="N"
            echo "  Non-interactive mode: keeping verify logs at $TARGET/.lowtech-tdd/"
            echo "  Remove manually with: rm -rf $TARGET/.lowtech-tdd/"
        fi
        if [[ "$yn" =~ ^[Yy]$ ]]; then
            rm -rf "$TARGET/.lowtech-tdd"
            echo "  ✓ Removed verify logs"
        else
            echo "  ✓ Kept verify logs"
        fi
    fi
}

# ── Run ────────────────────────────────────────────────────────
if $MCP_ONLY; then
    uninstall_mcp
elif $SKILL_ONLY; then
    uninstall_skill
else
    uninstall_skill
    uninstall_mcp
fi

echo ""
echo "╔══════════════════════════════════════╗"
echo "║           Uninstall complete        ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "Note: contract files (docs/specs/, docs/invariants/) and"
echo "verify.sh were not touched — remove manually if needed."
echo ""
echo "If you locked files with chmod 444, restore with:"
echo "  chmod 644 docs/specs/*.md docs/invariants/*.md"

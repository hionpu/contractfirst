#!/bin/bash
# contractfirst uninstaller
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
echo "║  contractfirst Removal  ║"
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

    SKILL_DIR="$TARGET/.claude/skills/contractfirst"

    if [[ -d "$SKILL_DIR" ]]; then
        rm -rf "$SKILL_DIR"
        # Remove parent skills/ dir only if now empty
        rmdir "$TARGET/.claude/skills" 2>/dev/null || true
        # Remove .claude/ dir only if now empty
        rmdir "$TARGET/.claude" 2>/dev/null && echo "  ✓ Removed $TARGET/.claude/" \
            || echo "  ✓ Removed $SKILL_DIR (other .claude/ files kept)"
    else
        echo "  ✓ No skill files found at $SKILL_DIR"
    fi

    PI_SKILL_DIR="${PI_SKILL_DIR:-$HOME/.pi/agent/skills/lowtech-tdd}"
    if [[ -d "$PI_SKILL_DIR" ]] && grep -q "contractfirst" "$PI_SKILL_DIR/SKILL.md" 2>/dev/null; then
        rm -rf "$PI_SKILL_DIR"
        echo "  ✓ Removed Pi native skill at $PI_SKILL_DIR"
    fi

    # Remove contractfirst import lines from CLAUDE.md / AGENTS.md / GEMINI.md
    for cfg in "$TARGET/CLAUDE.md" "$TARGET/claude.md" \
               "$TARGET/AGENTS.md" "$TARGET/agents.md" \
               "$TARGET/GEMINI.md" "$TARGET/gemini.md"; do
        if [[ -f "$cfg" ]] && grep -q "contractfirst\|SKILL\.md" "$cfg" 2>/dev/null; then
            sed -i.bak \
                -e '/# contractfirst/d' \
                -e '/@\.claude\/skills\/contractfirst\/SKILL\.md/d' \
                -e '/This project uses the contractfirst harness\./d' \
                -e '/Read \.claude\/skills\/contractfirst\/SKILL\.md/d' \
                "$cfg"
            rm -f "$cfg.bak"
            echo "  ✓ Cleaned $cfg"
        fi
    done
}

# ── Uninstall MCP ──────────────────────────────────────────────
uninstall_mcp() {
    echo "→ Removing MCP server..."

    MCP_DIR="$HOME/.local/share/contractfirst"

    # Deregister from Claude Code
    if command -v claude &>/dev/null; then
        claude mcp remove contractfirst 2>/dev/null \
            && echo "  ✓ Deregistered from Claude Code" \
            || echo "  ✓ Not registered with Claude Code (skipping)"
    fi

    # Deregister from Codex CLI (config.toml, not config.json)
    CODEX_CFG="$HOME/.codex/config.toml"
    if [[ -f "$CODEX_CFG" ]] && grep -q "contractfirst" "$CODEX_CFG"; then
        # Remove the [mcp_servers.contractfirst] block: header + the two key lines that follow.
        sed -i.bak '/^\[mcp_servers\.contractfirst\]/,/^args/d' "$CODEX_CFG"
        rm -f "$CODEX_CFG.bak"
        echo "  ✓ Deregistered from Codex CLI"
    fi

    # Deregister from Gemini CLI
    if has gemini; then
        python3 - <<'PYEOF'
import json, pathlib
cfg_path = pathlib.Path.home() / ".gemini" / "settings.json"
if cfg_path.exists():
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        cfg = {}
    if "contractfirst" in cfg.get("mcpServers", {}):
        cfg["mcpServers"].pop("contractfirst")
        cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        print("  OK Deregistered from Gemini CLI")
    else:
        print("  OK Not registered with Gemini CLI (skipping)")
PYEOF
    fi

    # Deregister from Pi MCP adapter
    PI_CFG="$HOME/.pi/agent/mcp.json"
    if [[ -f "$PI_CFG" ]]; then
        python3 - <<'PYEOF'
import json, pathlib
cfg_path = pathlib.Path.home() / ".pi" / "agent" / "mcp.json"
try:
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
except Exception:
    cfg = {}
servers = cfg.get("mcpServers", {})
changed = False
if "contractfirst" in servers:
    servers.pop("contractfirst")
    changed = True
legacy = servers.get("lowtech-tdd")
if isinstance(legacy, dict) and legacy.get("args") == ["-m", "contractfirst.server"]:
    servers.pop("lowtech-tdd")
    changed = True
if changed:
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print("  OK Deregistered from Pi MCP adapter")
else:
    print("  OK Not registered with Pi MCP adapter (skipping)")
PYEOF
    fi

    # Uninstall Python package
    if python3 -c "import contractfirst" &>/dev/null; then
        if command -v uv &>/dev/null; then
            uv pip uninstall contractfirst --quiet 2>/dev/null || true
        else
            pip3 uninstall contractfirst -y --quiet 2>/dev/null \
                || pip uninstall contractfirst -y --quiet 2>/dev/null \
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
    if [[ -d "$TARGET/.contractfirst" ]]; then
        if [[ -t 0 ]]; then
            read -rp "  Remove verify logs at $TARGET/.contractfirst/? [y/N] " yn < /dev/tty
        else
            yn="N"
            echo "  Non-interactive mode: keeping verify logs at $TARGET/.contractfirst/"
            echo "  Remove manually with: rm -rf $TARGET/.contractfirst/"
        fi
        if [[ "$yn" =~ ^[Yy]$ ]]; then
            rm -rf "$TARGET/.contractfirst"
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

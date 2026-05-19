#!/bin/bash
# contractfirst updater
# Usage: curl -fsSL https://raw.githubusercontent.com/hionpu/contractfirst/main/update.sh | bash
# Or run directly from local install:
#   bash ~/.local/share/contractfirst/update.sh [--skill-only] [--mcp-only] [--target ./my-project]

set -e

REPO="https://github.com/hionpu/contractfirst"
RAW="https://raw.githubusercontent.com/hionpu/contractfirst/main"
MCP_DIR="$HOME/.local/share/contractfirst"
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
echo "║      contractfirst Update      ║"
echo "╚══════════════════════════════════════╝"
echo ""

has() { command -v "$1" &>/dev/null; }
fetch() {
    if has curl; then curl -fsSL "$1"
    else wget -qO- "$1"; fi
}

# ── Update MCP server ──────────────────────────────────────────
update_mcp() {
    echo "→ Updating MCP server..."

    if [[ ! -d "$MCP_DIR/.git" ]]; then
        echo "  ✗ MCP server not installed at $MCP_DIR"
        echo "  Install first: curl -fsSL $REPO/raw/main/install.sh | bash"
        exit 1
    fi

    OLD_HEAD=$(git -C "$MCP_DIR" rev-parse HEAD)
    git -C "$MCP_DIR" pull --quiet
    NEW_HEAD=$(git -C "$MCP_DIR" rev-parse HEAD)

    if [[ "$OLD_HEAD" == "$NEW_HEAD" ]]; then
        TAG=$(git -C "$MCP_DIR" describe --tags --always 2>/dev/null || echo "${NEW_HEAD:0:7}")
        echo "  ✓ Already up to date ($TAG)"
    else
        N=$(git -C "$MCP_DIR" log --oneline "${OLD_HEAD}..${NEW_HEAD}" | wc -l | tr -d ' ')
        echo "  ✓ $N new commit(s):"
        git -C "$MCP_DIR" log --oneline "${OLD_HEAD}..${NEW_HEAD}" | sed 's/^/    /'
    fi

    # Reinstall package to pick up new dependencies or entry-point changes
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
            echo "  ✗ No pip/uv found — package not reinstalled"
            exit 1
        fi
    fi
    echo "  ✓ Package reinstalled"
}

# ── Update skill files ─────────────────────────────────────────
update_skill() {
    echo "→ Updating skill files..."

    SKILL_DIR="$TARGET/.claude/skills/contractfirst"

    if [[ ! -d "$SKILL_DIR" ]]; then
        echo "  ✗ Skill not installed at $SKILL_DIR"
        echo "  Install first: curl -fsSL $RAW/install.sh | bash --skill-only --target $TARGET"
        exit 1
    fi

    fetch "$RAW/skill/SKILL.md" > "$SKILL_DIR/SKILL.md"
    for ref in slicing spec-template platforms test-onboarding links project-types architecture-patterns; do
        fetch "$RAW/skill/references/$ref.md" > "$SKILL_DIR/references/$ref.md"
    done

    echo "  ✓ Skill updated → $SKILL_DIR/SKILL.md"
    echo "  ✓ References updated → $SKILL_DIR/references/"
}

# ── Run ────────────────────────────────────────────────────────
if $MCP_ONLY; then
    update_mcp
elif $SKILL_ONLY; then
    update_skill
else
    update_skill
    update_mcp
fi

echo ""
echo "╔══════════════════════════════════════╗"
echo "║           Updated!                  ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "Restart your CLI tool to pick up changes."
echo ""

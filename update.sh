#!/bin/bash
# contractfirst updater
# Usage: curl -fsSL https://raw.githubusercontent.com/hionpu/contractfirst/main/update.sh | bash
# Or run directly from local install:
#   bash ~/.local/share/contractfirst/update.sh [--skill-only] [--mcp-only] [--target ./my-project] [--cli claude,codex,...]

set -e

SCRIPT_VERSION="2026-05-26 15:25"

REPO="https://github.com/hionpu/contractfirst"
RAW="https://raw.githubusercontent.com/hionpu/contractfirst/main"
MCP_DIR="$HOME/.local/share/contractfirst"
SKILL_ONLY=false
MCP_ONLY=false
TARGET="."
CLI_LIST=""   # empty = all installed tools
REFS="slicing spec-template platforms test-onboarding links project-types architecture-patterns"

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
echo "║      contractfirst Update      ║"
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
    echo "Updating for: $(echo "$CLI_LIST" | tr ',' ' ')"
fi
echo ""

# With --cli: explicit list. Without: update all installed dirs.
cli_enabled() {
    local name="$1"
    if [[ -z "$CLI_LIST" ]]; then
        return 0  # no filter → treat all as enabled
    else
        echo "$CLI_LIST" | tr ',' '\n' | grep -qx "$name"
    fi
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
update_skill_files() {
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

update_skill() {
    echo "→ Updating skill files..."

    SKILL_DIR="$TARGET/.claude/skills/contractfirst"
    PI_SKILL_DIR="${PI_SKILL_DIR:-$HOME/.pi/agent/skills/contractfirst}"
    _updated=false

    # Shared skill dir — used by claude, codex, gemini, opencode (and pi via AGENTS.md)
    _shared_needed=false
    for _c in claude codex gemini opencode pi; do cli_enabled "$_c" && _shared_needed=true && break; done
    if $_shared_needed && [[ -d "$SKILL_DIR" ]]; then
        update_skill_files "$SKILL_DIR"
        echo "  ✓ Skill updated → $SKILL_DIR/SKILL.md"
        echo "  ✓ References updated → $SKILL_DIR/references/"
        _updated=true
    fi

    if cli_enabled pi && [[ -d "$PI_SKILL_DIR" ]]; then
        update_skill_files "$PI_SKILL_DIR"
        echo "  ✓ Pi native skill updated → $PI_SKILL_DIR/SKILL.md"
        _updated=true
    fi

    if ! $_updated; then
        echo "  ✗ Skill not installed at $SKILL_DIR or $PI_SKILL_DIR"
        echo "  Install first: curl -fsSL $RAW/install.sh | bash -s -- --skill-only --target $TARGET"
        exit 1
    fi
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

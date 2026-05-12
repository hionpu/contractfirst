# Link Management: Spec ↔ Invariant ↔ Interface ↔ Test

Every contract artifact must reference related artifacts via a `<!-- Links -->` block. This enables fast navigation and powers the MCP `verify_links` tool.

## Structure

```
Spec ←→ Invariants ←→ Interface ←→ Tests
  ↑_________________________________↓
```

Each file points to all related files. Links are bidirectional.

## Link Block Format

### Markdown files (specs, invariants)

```markdown
<!-- Links -->
- Specs: (this file) | [other-spec.md](../specs/other-spec.md)
- Invariants: [session-rules.md](../invariants/session-rules.md)
- Interfaces: [SessionStore.ts](../../src/interfaces/SessionStore.ts)
- Tests: [session-store.test.ts](../../tests/session-store.test.ts)
```

### Code files (interfaces, tests)

**Luau**
```lua
-- Links:
-- Specs: docs/specs/minigame-ui.md
-- Invariants: docs/invariants/session-rules.md
-- Interfaces: (this file)
-- Tests: src/Shared/SessionStore.spec.luau
```

**C# / TypeScript / Python**
```csharp
// Links:
// Specs: docs/specs/minigame-ui.md
// Invariants: docs/invariants/session-rules.md
// Interfaces: (this file)
// Tests: tests/SessionStoreTests.cs
```

**Elixir**
```elixir
# Links:
# Specs: docs/specs/minigame_ui.md
# Invariants: docs/invariants/session_rules.md
# Interfaces: (this file)
# Tests: test/session_store_test.exs
```

## Full Example

**`docs/specs/minigame-ui.md`**
```markdown
<!-- Links -->
- Specs: (this file)
- Invariants: [session-rules.md](../invariants/session-rules.md)
- Interfaces: [MiniGameUITypes.luau](../../src/Shared/Interfaces/MiniGameUITypes.luau)
- Tests: [MiniGameSessionStore.spec.luau](../../src/Shared/MiniGameSessionStore.spec.luau)
```

**`docs/invariants/session-rules.md`**
```markdown
<!-- Links -->
- Specs: [minigame-ui.md](../specs/minigame-ui.md), [inventory-system.md](../specs/inventory-system.md)
- Invariants: (this file)
- Interfaces: [MiniGameUITypes.luau](../../src/Shared/Interfaces/MiniGameUITypes.luau)
- Tests: [MiniGameSessionStore.spec.luau](../../src/Shared/MiniGameSessionStore.spec.luau)
```

## When to Update Links

### New test file created
```
1. "Which spec does this test verify?"
2. Add to that spec's Links → Tests
3. Add Links block to the test file header
```

### New invariant discovered
```
1. "Which category? Safety / Consistency / Boundary?"
2. Add rule to the relevant invariant file
3. Update Links → Invariants in all related specs
```

### New interface defined
```
1. Add Links block to the interface file
2. Add the interface path to the relevant spec's Links → Interfaces
```

## Ownership Rule

**Link creation and update is done by the human.** Links are contract artifacts. The AI may suggest missing links (via `verify_links` output) but must not silently rewrite link blocks.

Exception: human may explicitly delegate link writing to the AI for a specific session, in which case the AI writes and the human reviews before commit.

## What verify_links Checks

The MCP `verify_links` tool parses these blocks and checks:

| Category | What it means |
|----------|--------------|
| **missing** | Spec references a file that doesn't exist on disk |
| **stale** | Referenced file exists but has no back-link to this spec |
| **orphaned** | Invariant/interface/test file with no spec linking to it |

Run `verify_links` before declaring a feature done (Medium+).

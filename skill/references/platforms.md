# Platform Tool Mapping

The methodology is platform-independent. This file maps each contract concept to the right tool per platform.

## Interface Definition

| Platform | Tool |
|----------|------|
| Roblox (Luau) | `export type` + `--!strict` |
| Unity (C#) | `interface` + nullable reference types |
| Elixir | `@spec`, `@type`, `@callback` + Dialyzer |
| TypeScript | `interface` / `type` |
| Python | `Protocol`, `typing` module, `dataclass` |

### Examples

**Roblox (Luau)**
```lua
--!strict
export type ISessionStore = {
    isOpen: (self: ISessionStore, playerId: string) -> boolean,
    markOpen: (self: ISessionStore, playerId: string) -> (),
    markClosed: (self: ISessionStore, playerId: string) -> (),
}
```

**Unity (C#)**
```csharp
public interface ISessionStore
{
    bool IsOpen(string playerId);
    void MarkOpen(string playerId);
    void MarkClosed(string playerId);
}
```

**Elixir**
```elixir
defmodule SessionStore do
  @type player_id :: String.t()
  @callback is_open?(player_id()) :: boolean()
  @callback mark_open(player_id()) :: :ok
  @callback mark_closed(player_id()) :: :ok
end
```

**TypeScript**
```typescript
interface ISessionStore {
  isOpen(playerId: string): boolean;
  markOpen(playerId: string): void;
  markClosed(playerId: string): void;
}
```

**Python**
```python
from typing import Protocol

class SessionStore(Protocol):
    def is_open(self, player_id: str) -> bool: ...
    def mark_open(self, player_id: str) -> None: ...
    def mark_closed(self, player_id: str) -> None: ...
```

---

## Test Framework

| Platform | Framework | Run command |
|----------|-----------|-------------|
| Roblox | TestEZ | `rojo build` → Studio Test Runner |
| Roblox (CLI) | lune | `lune run tests/` |
| Unity | NUnit / Unity Test Framework | `dotnet test` |
| Elixir | ExUnit | `mix test` |
| TypeScript | Jest / Vitest | `npm test` |
| Python | pytest | `pytest` |

---

## CONTRACT Comment Format (inline invariants)

**Luau**
```lua
-- CONTRACT: SessionStore
-- INV-1: markOpen twice → isOpen still true (no accumulation)
-- INV-2: markClosed → isOpen is false
```

**C#**
```csharp
// CONTRACT: SessionStore
// INV-1: MarkOpen twice → IsOpen still true (no accumulation)
// INV-2: MarkClosed → IsOpen is false
```

**Elixir**
```elixir
# CONTRACT: SessionStore
# INV-1: mark_open/2 twice → is_open?/2 still true
# INV-2: mark_closed/2 → is_open?/2 is false
```

**TypeScript / Python**
```typescript
// CONTRACT: SessionStore
// INV-1: markOpen twice → isOpen still true
// INV-2: markClosed → isOpen is false
```

---

## verify.sh Composition

| Platform | typecheck | build | test | lint |
|----------|-----------|-------|------|------|
| Roblox | `luau-lsp check` | `rojo build` | TestEZ / lune | selene |
| Unity | Roslyn (MSBuild) | `dotnet build` | `dotnet test` | StyleCop / Rider |
| Elixir | `mix dialyzer` | `mix compile` | `mix test` | `mix credo --strict` |
| TypeScript | `tsc --noEmit` | `npm run build` | `npm test` | `eslint .` |
| Python | `mypy .` | — | `pytest` | `ruff check .` |

### verify.sh Template

```bash
#!/bin/bash
set -e

echo "=== Typecheck ==="
# <typecheck command>

echo "=== Build ==="
# <build command>

echo "=== Test ==="
# <test command>

echo "=== Lint ==="
# <lint command>

echo "=== All checks passed ==="
```

### Elixir Example

```bash
#!/bin/bash
set -e
echo "=== Compile ===" && mix compile --warnings-as-errors
echo "=== Test ===" && mix test
echo "=== Dialyzer ===" && mix dialyzer
echo "=== Credo ===" && mix credo --strict
echo "=== All checks passed ==="
```

### Unity Example

```bash
#!/bin/bash
set -e
echo "=== Build ===" && dotnet build --no-restore
echo "=== Test ===" && dotnet test --no-build
echo "=== All checks passed ==="
```

---

## Trust Boundary Contracts (Q2 reference)

| Platform | Mechanism |
|----------|-----------|
| Roblox | `RemoteEvent` / `RemoteFunction` — server never touches client GUI directly |
| Unity Netcode | `[ServerRpc]` / `[ClientRpc]` attributes |
| Unity Mirror | `[Command]` / `[ClientRpc]` |
| Elixir Phoenix | Channels, PubSub |
| TypeScript web | REST schema / tRPC / GraphQL |

# Test Onboarding: From Zero

**Goal**: Get a working verification loop running before committing to a test framework. Start with pure logic and the lightest possible tooling.

## Principle: Pure Logic First

Test things that have no engine/UI dependency:
- ✅ Session state (open/closed tracking)
- ✅ Inventory math (add/remove/count)
- ✅ Cooldown calculation
- ✅ State machine transitions
- ✅ Damage/stat formulas

Avoid on day one:
- ❌ UI integration tests
- ❌ Rendering output validation
- ❌ Network synchronization

## Level 0: Manual Checklist

Before any code exists, write the checklist that defines "it works."

```markdown
## Manual Verification Checklist: Lobby UI

- [ ] Interacting with the minigame object opens the UI
- [ ] Interacting again while open does nothing (no duplicate)
- [ ] Closing the UI cleans up session state
- [ ] No errors in console during any of the above
```

This is your Done Definition. Do not skip it.

## Level 1: Inline Asserts

Extract pure logic into a module. Write a test runner that uses `assert` / `assertEquals`.

**Roblox (Luau)**
```lua
-- tests/SessionStore.test.luau
local SessionStore = require("../src/Shared/SessionStore")

local function assertEquals(actual, expected, msg)
    if actual ~= expected then
        error(("FAIL: %s (expected %s, got %s)"):format(
            msg, tostring(expected), tostring(actual)))
    end
    print("PASS: " .. msg)
end

local store = SessionStore.new()
assertEquals(store:isOpen("p1"), false, "starts closed")
store:markOpen("p1")
assertEquals(store:isOpen("p1"), true, "open after markOpen")
store:markOpen("p1")
assertEquals(store:isOpen("p1"), true, "still open after second markOpen")
store:markClosed("p1")
assertEquals(store:isOpen("p1"), false, "closed after markClosed")
print("=== All tests passed ===")
```

**Unity (C#) — no framework**
```csharp
public static class SimpleTestRunner
{
    public static void Run()
    {
        var store = new SessionStore();
        Debug.Assert(!store.IsOpen("p1"), "starts closed");
        store.MarkOpen("p1");
        Debug.Assert(store.IsOpen("p1"), "open after MarkOpen");
        store.MarkClosed("p1");
        Debug.Assert(!store.IsOpen("p1"), "closed after MarkClosed");
        Debug.Log("=== All tests passed ===");
    }
}
```

**Python — no framework**
```python
store = SessionStore()
assert not store.is_open("p1"), "starts closed"
store.mark_open("p1")
assert store.is_open("p1"), "open after mark_open"
store.mark_closed("p1")
assert not store.is_open("p1"), "closed after mark_closed"
print("=== All tests passed ===")
```

**Key rule**: The assert values (expected) are written by the human. The AI implements the module to pass them. Never reverse this.

## Level 2: Test Framework

When you have 5+ assert-based tests, migrate to a framework. Migration rule: **tests (assertions) stay the same; only the wrapper syntax changes.**

**Roblox → TestEZ**
```lua
-- Before
assertEquals(store:isOpen("p1"), false, "starts closed")

-- After
it("starts closed", function()
    local store = SessionStore.new()
    expect(store:isOpen("p1")).to.equal(false)
end)
```

**Unity → NUnit**
```csharp
// Before
Debug.Assert(!store.IsOpen("p1"), "starts closed");

// After
[Test]
public void StartsClosed()
{
    var store = new SessionStore();
    Assert.IsFalse(store.IsOpen("p1"));
}
```

**Python → pytest**
```python
# Before
assert not store.is_open("p1"), "starts closed"

# After
def test_starts_closed():
    store = SessionStore()
    assert not store.is_open("p1")
```

## Level 3: verify.sh Integration

Once tests run from CLI, add them to `verify.sh`:

```bash
#!/bin/bash
set -e
echo "=== Test ===" && <test command>
echo "=== All checks passed ==="
```

Then add typecheck, lint, build as the project matures.

## Onboarding Checklist

- [ ] Write manual checklist (Level 0) before any code
- [ ] Extract one pure logic module (no engine/UI dependency)
- [ ] Write 3+ assert-based tests (Level 1) — human writes the expected values
- [ ] Run tests and confirm pass
- [ ] Ask AI to implement the module to pass the tests
- [ ] Migrate to test framework when 5+ tests exist (Level 2)
- [ ] Add to verify.sh (Level 3)

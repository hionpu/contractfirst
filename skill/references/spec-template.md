# Spec Document Template

Use this template for Medium+ features. Save as `docs/specs/<feature-name>.md`.

For Small features, a single paragraph is sufficient — do not force this template.

---

## Template

```markdown
<!-- Links -->
- Specs: (this file)
- Invariants: [<invariant-name>.md](../invariants/<invariant-name>.md)
- Interfaces: [<InterfaceFile>](../../src/<path>/<InterfaceFile>)
- Tests: [<test-file>](../../<path>/<test-file>)

# Spec: <Feature Name>

## Goal
<!-- One paragraph. What user problem does this solve? What changes for the user? -->

## Non-goals
<!-- What this feature explicitly does NOT do. Write this defensively — it protects scope. -->
- ...
- ...

## Out of Scope
<!-- Behaviors excluded from this iteration. May be addressed in a future slice. -->
- ...

## User Flow
<!-- Step-by-step from the user's perspective. Numbered list. -->
1. ...
2. ...
3. ...

## Edge Cases
<!-- Failure modes, boundary conditions, concurrent access, repeat actions. -->
- ...

## Acceptance Criteria
<!-- Each AC must be a verifiable yes/no statement. 3–7 items. -->
- [ ] AC-1: ...
- [ ] AC-2: ...
- [ ] AC-3: ...

## Done Definition
<!-- What state = this feature is complete? -->
- All AC above pass
- verify.sh passes (typecheck + test + lint)
- Links section complete
- Human has reviewed and approved contract artifacts

## Risks / Notes
<!-- Trust boundary concerns, performance budget, concurrency, security. -->
- ...
```

---

## Filling Guidelines

**Goal**: Write from the user's perspective. "Player can X" not "System implements Y."

**Non-goals**: Be aggressive here. If something is NOT in this slice, name it explicitly. This is the primary defense against scope creep.

**AC format**: Use "Given/When/Then" mentally, even if you don't write it out.
- ✅ "When the player opens the lobby while already in one, the second open is ignored"
- ❌ "Handle duplicate opens" (not verifiable)

**User Flow**: Write from the user's perspective, numbered, one observable action per step.
Never describe internal implementation steps — only what the user sees or does.

**Edge Cases**: At minimum cover: duplicate action, concurrent use, boundary value, error path.

**Risks / Notes**: Flag trust boundary crossings (Q2), performance budget assumptions,
and anything that may require a Safety or Boundary invariant.

**Done Definition**: Always include `verify.sh passes`. Manual steps, if any, must be listed explicitly and marked as "confirmed" or "handed off."

---

## Minimal Version (Small feature)

```markdown
<!-- Links -->
- Specs: (this file)
- Interfaces: [<InterfaceFile>](../../src/...)
- Tests: [<test-file>](../../tests/...)

When a player interacts with the minigame object, the lobby UI opens.
If the UI is already open, the interaction is ignored.
On close, session state is cleaned up.
```

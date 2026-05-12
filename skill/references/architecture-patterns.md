# Architecture Pattern Invariants

When a project follows an architectural pattern (MVC, MVVM, ECS, Flux/Redux, Clean / Hexagonal), the pattern's structural rules become **Boundary invariants**. Document them once in `docs/invariants/architecture-<pattern>.md` and reference from every spec that touches the pattern.

## Why Patterns Become Invariants

- The pattern's rules are "always / never" by definition (e.g., "View never writes to Model").
- Without explicit invariants, AI implementations drift away from the pattern within a few iterations.
- New modules need a clear template; invariants make the template machine-readable for the AI and human-readable for reviewers.

## When NOT to Document an Architecture Pattern

- The codebase has no consistent pattern (legacy / spike / prototype).
- The pattern is informal and rarely violated (small project, single author, low risk).
- Documenting would invent a constraint that doesn't reflect reality.

Document the pattern **only when violations are an actual risk worth catching**.

---

## MVC

`docs/invariants/architecture-mvc.md`

```markdown
- [Boundary] View never modifies Model directly. Mutations always go through Controller.
- [Boundary] Model never references View. Dependency direction: View → Controller → Model.
- [Boundary] Controller is the only layer holding references to both Model and View.
- [Consistency] One View binds to exactly one Controller (no shared controllers across views).
```

## MVVM (WPF, Avalonia, MAUI, Xamarin, Knockout)

`docs/invariants/architecture-mvvm.md`

```markdown
- [Boundary] View binds to ViewModel via data binding only — no direct property writes from code-behind.
- [Boundary] ViewModel never references View types (no `Window`, `Control`, `FrameworkElement`, `View` in VM signatures).
- [Boundary] Model is engine-agnostic — no `INotifyPropertyChanged`, no `Dispatcher`, no UI-thread assumptions in Model layer.
- [Consistency] Commands (`ICommand`) are the only mutation entry point from View into ViewModel.
- [Performance] Long-running work in ViewModel runs on a background thread; results marshal back via the binding system, never via blocking calls.
```

## ECS (Unity DOTS, Bevy, Flecs, custom)

`docs/invariants/architecture-ecs.md`

```markdown
- [Boundary] Components hold data only. No methods beyond constructors and pure getters.
- [Boundary] Systems hold logic only. They read and write Components but contain no instance state.
- [Boundary] Entities are containers — they have no behavior of their own.
- [Performance] Each System runs every frame (or every tick). Keep complexity O(n) over its component query.
- [Consistency] A component type is owned by exactly one System for writes; multiple Systems may read it.
```

## Flux / Redux / Elm-style state

`docs/invariants/architecture-flux.md`

```markdown
- [Boundary] State mutates only inside the reducer. Views and async handlers never mutate state directly.
- [Boundary] Views dispatch Actions; they do not call reducers.
- [Consistency] Reducers are pure: same `(state, action)` always produces the same new state, with no I/O.
- [Safety] Side effects (API calls, storage writes, navigation) live in Middleware / Effects / Sagas — never in reducers or components.
- [Consistency] State-shape changes are migrations — never mutate state shape silently.
```

## Clean / Hexagonal (Ports & Adapters)

`docs/invariants/architecture-hexagonal.md`

```markdown
- [Boundary] Domain layer has no dependency on Application, Infrastructure, or UI layers.
- [Boundary] Application layer depends only on Domain.
- [Boundary] Infrastructure depends on Application interfaces (ports), not the other way around.
- [Consistency] All cross-layer communication uses interfaces defined by the inner layer ("dependency inversion").
- [Boundary] No framework / driver / DB type leaks into the Domain layer.
```

---

## Linking Pattern Invariants from a Spec

A spec touching both an architecture pattern and a domain rule references both:

```markdown
<!-- Links -->
- Specs: (this file)
- Invariants:
  - [architecture-mvvm.md](../invariants/architecture-mvvm.md)   ← architecture
  - [order-rules.md](../invariants/order-rules.md)               ← domain
- Interfaces: [IOrderViewModel.cs](../../src/ViewModels/IOrderViewModel.cs)
- Tests: [OrderViewModelTests.cs](../../tests/OrderViewModelTests.cs)
```

The AI must satisfy **both** architecture and domain invariants. If a domain rule and an architecture rule appear to conflict, **stop and report** — do not silently violate one to satisfy the other.

## Mixing Multiple Patterns in One Project

A single project may use different patterns in different areas (MVVM in the desktop UI + Clean Architecture in the service layer). Each gets its own `architecture-<pattern>.md` file. Each spec links only the pattern files relevant to its scope.

If two patterns produce contradictory boundary rules at their interface (e.g., MVVM ViewModel calling into a Hexagonal use case), define a third invariant file for the **integration boundary** rather than weakening either pattern.

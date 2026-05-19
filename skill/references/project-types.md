# Project Type Guidance

A project's type determines how the harness weights automatic vs manual verification, which invariant categories dominate, and how Acceptance Criteria are structured. Determine type **once per project**, on first invocation.

## The Three Types

| Type | Typical projects | Verify Gate emphasis |
|------|------------------|----------------------|
| **logic-heavy** | Backend services, libraries, CLIs, parsers, data pipelines | Automatic checks dominate (typecheck + test + lint). Manual is rare. |
| **ui-heavy** | WPF / Qt / Avalonia / MAUI desktop, Unity / Roblox / Godot game content, SwiftUI / Compose / Flutter mobile | Manual checklist is first-class. Visual, interaction, focus, animation cannot be automated. |
| **mixed** | Full-stack web, game with networked backend, desktop app with rich business logic | Track automatic and manual checks separately; both block "done". |

## Inference Signals

The AI proposes a type by scanning the codebase. Confirm before proceeding.

### Logic-heavy signals
- Backend frameworks: Django, FastAPI, Express, Phoenix, ASP.NET Core (API), Spring Boot
- CLI / library project layout (`src/` + `tests/`, no view/asset trees)
- Source extensions dominated by `.py`, `.ts`, `.go`, `.rs`, `.ex`, `.java`
- No or negligible `.xaml`, `.qml`, `.tscn`, `.unity`, `.rbxlx`, `.swift` (UI), `.kt` (Compose)

### UI-heavy signals
- Desktop framework files: `.xaml` (WPF / Avalonia / MAUI), `.qml` / `.ui` (Qt), `.axaml` (Avalonia)
- Game engine assets: `.unity`, `.prefab`, `.tscn`, `.gd`, `.rbxlx`, `.rbxl`, large `.luau` GUI modules
- Mobile UI: SwiftUI `View` types, Jetpack Compose `@Composable`, React Native / Flutter screen-heavy layout
- High view/scene/asset count vs pure-logic file count

### Mixed signals
- Both backend and frontend trees in one repo (`server/` + `client/`, `api/` + `web/`, etc.)
- WPF / MAUI app whose ViewModels contain non-trivial domain logic
- Game project with a Node/Elixir/Go backend in the same repo
- More than ~30% of code on each side of the UI/logic split

## Per-Type Behavior

### Logic-heavy

- **Verify Gate**: automatic checks (typecheck + test + lint + build) are sufficient for "done" in the vast majority of features.
- **Manual checks**: limited to integration smoke (DB seed correctness, external API sanity, prod-config dry run).
- **Invariant categories most common**: Safety (data integrity, idempotency, auth), Consistency (state relationships), Boundary (service/module separation).
- **AC structure**: single list. Every AC is verifiable by automated test or shell command.

### UI-heavy

- **Verify Gate**: automatic checks are necessary but not sufficient. The manual checklist is the **primary** verification for the visual / interaction layer.
- **Manual checks always required**:
  - Visual layout (alignment, spacing, contrast, dark mode if applicable)
  - Interaction feel (responsiveness, animation timing, input lag, gesture conflicts)
  - Focus and keyboard navigation
  - Empty / loading / error / offline states visible to the user
  - Repeat / concurrent input edge cases (double-click, rapid taps, race-y gestures)
- **Invariant categories most common**: Boundary (server↔client, view↔logic, UI thread), Performance (frame budget, event-listener leak prevention, asset load), Consistency (one modal at a time, focus invariants, modal stack ordering).
- **AC structure**: split into **logic-AC** (testable assertions) and **UX-AC** (manual confirmation items). Both must pass. UX-AC items must list how a human will confirm them ("playtest 3 minutes", "screenshot at 1920×1080 + 4K").
- **A `verify.sh` pass without a confirmed manual checklist is not done.**

### Mixed

- **Verify Gate**: report automatic AND manual sections separately in the implementation report. Both block "done".
- **Manual checks**: scoped to the UI surface only. Backend-only changes follow logic-heavy rules; UI-touching changes follow ui-heavy rules.
- **Invariant categories**: full Safety / Consistency / Boundary / Performance mix; expect 5+ invariants in a Large feature.
- **AC structure**: split per layer when relevant — for example "API contract AC" + "UI behavior AC" + "End-to-end AC". Cross-layer ACs that require both sides to be in place go in the end-to-end group.

## Detection Protocol (strict order)

The protocol is designed so that **only the first session pays any cost**. Every subsequent session reads the persisted value from the already-loaded agent-instructions file — no scan, no prompt, no extra tokens.

### Step 1 — Cache check (every session)

Look in the loaded `CLAUDE.md` / `AGENTS.md` / `GEMINI.md` for:

```
<!-- contractfirst: project_type=X -->
```

where `X` ∈ `{logic-heavy, ui-heavy, mixed}`. If present, **use that value silently and stop**. Do not scan the codebase. Do not ask the user.

### Step 2 — Inference (only if cache absent)

Scan the codebase for the signals listed above. Build a short proposal.

### Step 3 — Confirm with the user

```
I infer this is a <type> project based on:
- <signal 1>
- <signal 2>
- <signal 3>

Project Type: <type>  (logic-heavy / ui-heavy / mixed)
Confirm, or correct with one of the other two?
```

### Step 4 — Persist

Append exactly one line to the agent-instructions file:

```
<!-- contractfirst: project_type=ui-heavy -->
```

From the next session onward, Step 1 short-circuits to a free read.

## Re-evaluation

Re-run inference only if the codebase composition shifts substantially:
- A logic-heavy backend grows a desktop or web client.
- A ui-heavy game project adds a server-authoritative backend.
- A mixed project drops one side entirely.

Otherwise, Project Type is stable across the life of the project.

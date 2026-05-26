---
name: contractfirst
description: Contract-enforced implementation harness for AI-assisted coding. Apply this skill whenever the user wants to implement a feature, fix a bug, or refactor code. Enforces Socratic clarification, ambiguity scoring, contract definition (Spec/Invariant/Interface/Test), strict implementation boundaries, and human skill preservation. Skip for pure Q&A.
---

# contractfirst: Contract-Enforced Implementation Harness

## Core Philosophy

> **The human owns the contract. The AI iterates on implementation. The Harness enforces the boundary.**

This workflow is not just about writing code faster; it prevents human skill degradation and maintains strict architectural boundaries. The contract has four parts:
1. **Spec** — what it does (requirements, AC, Done definition)
2. **Invariant** — conditions that must never break (Safety, Consistency, Boundary, Performance)
3. **Interface** — input/output shapes and module boundaries
4. **Test/Verify** — automated or manual validation

## Human Skill Preservation (Anti-Degradation)

To prevent the human from becoming a mere "approval button" and losing debugging or design muscles:

- **Rule H1 (Human-Authored Zones):** `docs/specs/`, `docs/invariants/`, public interface signatures, and test assertion blocks are human-owned. AI may propose; human must finalize.
  *Rationale: typing these artifacts directly preserves syntax instincts, library familiarity, and debugging muscle. Delegating them entirely causes skill atrophy over time.*
- **Rule H2 (Hand-Code Quota):** For Medium+ tasks, the human explicitly hand-codes at least one critical unit (core pure logic, crucial adapter, or test assertion).
- **Rule H3 (Explain Before Merge):** Before concluding a Medium+ feature, ask the human to briefly explain the root cause of any complex debugging fix or the core logic of the AI's implementation.
- **Rule H4 (Debugging Split):** On *contract-sensitive* verify failures (invariant / interface / test / spec related), the AI provides *root cause analysis only*. Do not write the patch until the human understands the cause and approves the fix strategy. Routine failures (typos, lint, trivial type errors) are exempt — fix and report.

## Project Type (session-level, one-time)

Look in the loaded agent-instructions file (`CLAUDE.md` / `AGENTS.md` / `GEMINI.md`) for `<!-- contractfirst: project_type=X -->` where `X` ∈ `{logic-heavy, ui-heavy, mixed}`. If present, use it silently. If absent, follow the detection + persistence protocol in `references/project-types.md` (one-time cost per project).

| Type | Examples | Verify Gate emphasis |
|------|----------|----------------------|
| **logic-heavy** | backend, library, CLI, parser, data pipeline | Automatic checks dominate; manual is rare. |
| **ui-heavy** | WPF / Qt / Avalonia desktop, Unity / Roblox / Godot game content, mobile UI | Manual checklist is **primary** — visual, interaction, focus, animation cannot be automated. Use `track_manual_checks`. |
| **mixed** | full-stack web, game with networked backend, desktop app with rich domain layer | Track automatic and manual checks separately; both block "done". |

Project Type adjusts: Verify Gate weighting, which invariant categories dominate, and whether AC splits into logic-AC vs UX-AC (mixed / ui-heavy: yes).

## Scale Triage (Risk & Boundary Based)

Do not measure scale by time. Measure by risk:

| Q | Question | Escalates toward |
|---|----------|-----------------|
| Q0 | Does this touch a shared interface, schema, or public API? | Medium+ |
| Q1 | Does this involve state that persists or accumulates? | Small+ |
| Q2 | Does this cross a trust boundary (server↔client, DB↔app)? | Large |
| Q3 | Do 3+ independent concerns need to collaborate? | Large |

| Scale | Definition & Scope | Required Artifacts |
|-------|--------------------|--------------------|
| **Micro** | Pure/small change, no persistent state, no shared boundary | Fix directly; at minimum add/confirm a type signature and 1–2 smoke tests |
| **Small** | Local state or one-module behavior | Interface/signature + CONTRACT comments + verification |
| **Medium** | Shared interface change, multiple files, moderate coordination | Simplified spec + interface + CONTRACT + verification (Plan optional) |
| **Large** | Trust boundary, multiple domains, high-risk behavior | Full spec + invariants + interface + verification + Plan + Reviewer pass |

> **Note**: Scale is judged by **risk and boundary complexity**. Slice size (in Step 1) is judged by **delivery size** (4–8 hours, 3–7 AC). Do not confuse the two.

## Clarification Gate (Socratic Loop)

Do not proceed to contract or code until clarity is sufficient.

### For Micro / Small (Ambiguity Tripwire)
Ask 2–3 quick questions to establish boundaries:
1. What is the single observable outcome of this change?
2. What existing behavior must *not* be affected?
3. How will we verify this worked?

All three must be answered before proceeding. No scoring required.

### For Medium / Large (Full Socratic Loop)
Evaluate the request against the clarity rubric below. Ask targeted questions for missing or weak areas.

- **Goal**: Is the core value clear?
- **Non-goals / Out-of-scope**: Are boundaries explicitly defined?
- **Acceptance Criteria**: Is every AC a verifiable yes/no statement?
- **Edge Cases**: Are failure modes defined?
- **Invariants**: Are there Safety/Consistency rules to maintain?

### Ambiguity Scoring (Medium / Large) — Audited Two-Step

Score each dimension from 0.0 to 1.0. Each score must be paired with a verbatim quote from the user's request (≥ 8 chars), or the literal token `none` if the user said nothing about that dimension. `none`-evidence scores are capped at ≤ 0.30.

| Dimension | Weight |
|-----------|--------|
| Goal clarity | 0.40 |
| Constraint clarity | 0.30 |
| Success criteria clarity | 0.30 |

```
Ambiguity = 1 − Σ(score × weight)
```

Rules:
- Proceed only when **Ambiguity ≤ 0.20** AND **Blocking question count = 0**
- Boundary/risk dimensions are covered separately by Scale Triage Q0–Q3 — do not double-count

**You (Planner / Agent A) are not allowed to confirm your own ambiguity score.** A sub-agent must audit the evidence quotes before the gate decision is finalized. Use the audited two-step:

#### Step 1 — Draft

Call `draft_ambiguity_score(project_root, user_prompt_verbatim, scores, evidence, blocking_questions, open_questions)`.

`user_prompt_verbatim` is the user's original feature request copied **exactly** (not your summary). MCP returns:
- `draft_id`
- `audit_token`
- `auditor_prompt_markdown` — the prompt to give the Auditor sub-agent

#### Step 2 — Dispatch Auditor (CLI-native sub-agent)

Use your CLI's native sub-agent mechanism. Pass `auditor_prompt_markdown` verbatim:

| CLI | Dispatch |
|-----|----------|
| Claude Code | `Task` tool with `subagent_type="general-purpose"`, `prompt=<auditor_prompt_markdown>` |
| Pi | bash: `pi -p --no-tools "<auditor_prompt_markdown>"` (capture stdout) |
| Codex CLI | bash: `codex exec "<auditor_prompt_markdown>"` (verify your CLI's non-interactive flag) |
| Gemini CLI | bash: `gemini -p "<auditor_prompt_markdown>"` (verify) |

Capture the sub-agent's full text output as `auditor_transcript`.

#### Step 3 — Commit

Call `commit_ambiguity_audit(project_root, draft_id, auditor_transcript)`. Pass the transcript **verbatim** — do not summarize, paraphrase, or edit. MCP extracts the verdict JSON (must contain the matching `audit_token`), forces rejected dimensions to score 0.0, and returns the final `proceed` decision.

Print the returned `report_markdown` verbatim before continuing.

#### What the audit catches

- Fabricated evidence quotes ("user said X" when user didn't)
- Forced readings (mapping unrelated user words to a dimension)
- Inflated `none`-evidence scores
- Tampered transcripts (missing `audit_token` → rejected)

Tampering surfaces in `.contractfirst/gates.jsonl`. The audit can be skipped by fabricating a transcript with a valid token, but the absence of a real sub-agent invocation in the session log makes this detectable on human review.

## The Workflow

```text
[Step 0] Project Type           ← Once per project (infer + confirm)
[Step 1] Vertical Slicing       ← Before Scale Triage, if feature too broad for one contract
[Step 2] Scale Triage           ← Always (per slice)
[Step 3] Clarification Gate     ← Always (Tripwire for Small, Full+score for Medium+)
[Step 4] Write Spec             ← Medium+
[Step 5] Define Invariants      ← Small (Comments) / Large (Files)
[Step 6] Fix the Interface      ← Small+ (Human must finalize)
[Step 7] Write Plan             ← Large required / Medium optional
[Step 8] Implement              ← Always (Follow Rule H2 & H4)
[Step 9] Reviewer Pass          ← Large
[Step 10] Verify Gate           ← Always (Pass required)
```

## Step 1: Vertical Slicing

**When**: Before Scale Triage, when the requested feature is too broad to fit in one contract or one slice.

Split into **vertical slices** (never horizontal).

- ❌ Horizontal: "DB layer → business logic → UI" (nothing works until all three done)
- ✅ Vertical: "minimal end-to-end slice → add edge cases → next behavior"

Each slice: 4–8 hrs, 3–7 AC, delivers standalone user value. Then run Scale Triage on each slice independently.

> Details: `references/slicing.md`

## Step 4–6: Contract Artifacts (by scale)

- **Spec** (Medium+): `docs/specs/<feature>.md` with Goal, Non-goals, Out-of-scope, AC, Done. (Small: 1 paragraph)
- **Invariants** (Medium: inline `CONTRACT:` comments / Large: `docs/invariants/<domain>.md`) — see Invariants subsection below
- **Interface** (Small+): signatures fixed before any implementation. Human finalizes.
- **Verification** (Small+): pick level — Manual checklist / Inline asserts / Test framework / `verify.sh`. Start at whatever level the infra supports.

> Templates: `references/spec-template.md`, `references/platforms.md`, `references/test-onboarding.md`

### Invariants

Examples:
- "A player's balance is always ≥ 0 (server-side)"
- "A player's minigame UI is always open at most once (shared Store)"
- "The server never invokes client GUI APIs (boundary)"
- "Event listeners are always disconnected on session end (client module)"

Invariant categories:
- **Safety**: breach causes data loss, duplicate reward, or privilege escalation
- **Consistency**: state/data relationship (balance ≥ 0, one UI per player, no duplicates)
- **Boundary**: layer responsibility separation (server never touches client GUI)
- **Performance**: resource/frame budget (event listener leak prevention, per-frame creation limit)

Writing rules:
- Use "always" or "never" — not "should" or "it's good if"
  - ❌ "UI should only open once per player"
  - ✅ "A player's minigame UI is always open at most once"
- State where it is enforced: "(server-side)", "(shared Store)", "(client module)"
- Migrate to automated tests over time — start as prose, graduate to assertions

## Step 7: Plan

**Large**: required. **Medium**: only when ambiguity or risk justifies it.

Plan includes: files to change, new signatures, dependency changes, risk areas.

Use Claude Code plan mode. Write `PLAN.md`. Do not write implementation until user approves.

## Implementation Rules (The Harness)

1. **Read-Only Contracts:** Do not modify Spec, Invariant, Interface, or Test artifacts without explicit user approval.
2. **Link Management:** If `Spec ↔ Invariant ↔ Interface ↔ Test` links are missing or stale, report them. **Do not silently rewrite link blocks** unless the human explicitly delegates it.
3. **Stop on Ambiguity:** Do not guess implementation details. If the contract contradicts itself, stop and report.
4. **No Scope Creep:** Do not implement anything not explicitly defined in the AC.
5. **Verify Gate:** Run `./verify.sh` (or equivalent). One failure = not done.

Report format after implementation:
```
Changes:
- [file]: [summary]

Verification:
- typecheck: pass/fail
- tests: X/Y passed
- lint: pass/fail
- manual: confirmed / handed off

Links: complete / missing: [list]

Unresolved:
- (list any blockers)
```

## Reviewer Pass (Large only)

Switch to Reviewer mode (new session or explicit mode switch). Reviewer reads the diff but does **not** judge style or redesign architecture. Checks only:
- ✅ No invariant violated
- ✅ Non-goals / out-of-scope not touched
- ✅ Contract artifacts not modified without approval
- ✅ No new security / performance / concurrency risk
- ✅ All required links present

## Verify Gate

Done means:
- all required automatic checks pass, AND
- all declared manual checks are either explicitly confirmed or explicitly handed off

One failed check = not done.
One unconfirmed required manual check = not done.

**How to enforce this with MCP tools:**

1. For any feature with manual verification items (always, for ui-heavy / mixed), `track_manual_checks(op="declare", checks=[...])` at the start of implementation.
2. Call `run_verify(feature="<slug>")` — when `feature` is set, `run_verify` consults the ledger and returns `overall: pending_manual` whenever required manual checks remain pending, even if `automatic_overall: pass`. A green automatic run cannot be reported as done while items are pending.
3. As the human confirms each item, the AI calls `track_manual_checks(op="confirm", check_id=...)` to record it. Use `op="handoff"` (with a `note`) when the check is explicitly handed off to another party — this also counts as resolved.

For **ui-heavy** projects, the manual-checklist clause is not a backstop — it is the **primary** verification mechanism for the visual / interaction layer. A `verify.sh` pass without a confirmed manual checklist is **not done**. See `references/project-types.md` for the full per-type breakdown.

## Contract Change Protocol

A contract change is allowed only when:
- Requirements changed after the contract was written
- A contradiction in the contract was discovered
- The contract is provably too strict to implement correctly

**AI must never apply the change directly.** When a contract change seems necessary:
1. Stop implementation
2. Report: reason, affected artifacts, tests needing update, re-verification required
3. Wait for explicit user approval
4. Only then update the contract and resume

## Failure Handling

When verification fails:
1. Analyze root cause first. Do not patch blindly.
2. If an invariant is violated, revert or rethink — do not layer fixes on top.
3. After any fix, rerun the **full** relevant verification set, not only the last failed check.
4. If the failure suggests the contract is wrong, stop and follow Contract Change Protocol.
5. For contract-sensitive failures (per Rule H4), present root cause analysis only and wait for human approval before writing the patch. Routine failures (lint, trivial typos, type errors) may be fixed directly and reported.

## Anti-patterns

- ❌ Writing code before interface/contract is clear
- ❌ Modifying tests to make them pass
- ❌ Changing interfaces without explicit human approval
- ❌ Reporting "done" without running required verify steps
- ❌ Patching over an invariant violation instead of fixing root cause
- ❌ Silently updating link blocks or contract artifacts
- ❌ Proceeding past the Clarification Gate without printing the Ambiguity Report (Medium+)
- ❌ Inflating ambiguity scores without verbatim evidence quotes (the `score_ambiguity` tool will reject this)
- ❌ Skipping the Auditor sub-agent and synthesizing a fake `auditor_transcript` to pass to `commit_ambiguity_audit` (audit token enforcement + gates.jsonl audit trail expose this)
- ❌ Modifying / summarizing / "cleaning up" the Auditor transcript before passing it to `commit_ambiguity_audit` (pass it VERBATIM)
- ❌ Reporting a feature as done while `run_verify` returns `overall: pending_manual` (ui-heavy / mixed)
- ❌ Writing a contract-sensitive fix patch before human approves the root cause (Rule H4)

## Response Format

When applying this skill:
1. State the scale judgment (run Q0–Q3, explain result)
2. Run Clarification Gate — for Medium+, print the full Ambiguity Report in the fixed template above
3. List which workflow steps apply for this scale
4. Execute each step, showing artifacts
5. Block on user input whenever a contract decision is required

Ask rather than assume whenever scope or spec is unclear.

## Reference Files

Load only when needed for the relevant step:

- `references/slicing.md` — vertical slice decomposition guide
- `references/spec-template.md` — spec document template
- `references/platforms.md` — platform tool mapping (Roblox / Unity / Elixir / TS / Python)
- `references/test-onboarding.md` — building test infra from zero
- `references/links.md` — Spec ↔ Invariant ↔ Interface ↔ Test link management
- `references/project-types.md` — per-project-type Verify Gate adjustments (logic-heavy / ui-heavy / mixed)
- `references/architecture-patterns.md` — MVC / MVVM / ECS / Flux / Hexagonal invariant templates

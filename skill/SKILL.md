---
name: contractfirst
description: Contract-enforced implementation harness. Apply when implementing features, fixing bugs, or refactoring. Skip for Q&A.
---

# contractfirst

> Human owns contract. AI iterates implementation. Harness enforces boundary.

## Human Rules (all scales)

- **H1** `docs/specs/`, `docs/invariants/`, public interface signatures, test assertion blocks — human-owned. AI proposes; human finalizes.
- **H2** Medium+: human hand-codes at least one critical unit.
- **H3** Medium+: before closing, ask human to explain core logic or root cause of any complex fix.
- **H4** Contract-sensitive failures (invariant / interface / test / spec): root cause only — no patch until human approves fix strategy. Routine (lint, typo): fix and report.

## Project Type (once per project)

Check agent-instructions file for `<!-- contractfirst: project_type=X -->` (X ∈ logic-heavy, ui-heavy, mixed). If absent, see `references/project-types.md`.

| Type | Verify Gate emphasis |
|---|---|
| logic-heavy | Automatic checks dominate |
| ui-heavy | Manual checklist is **primary** — `track_manual_checks` required |
| mixed | Both automatic and manual block "done" |

## Scale Triage

| Q | Does this… | Escalates |
|---|---|---|
| Q0 | Touch a shared interface / schema / public API? | Medium+ |
| Q1 | Involve persisted or accumulated state? | Small+ |
| Q2 | Cross a trust boundary (server↔client, DB↔app)? | Large |
| Q3 | Require 3+ independent concerns to collaborate? | Large |

| Scale | Scope | Required artifacts |
|---|---|---|
| **Micro** | No persistent state, no shared boundary | Type signature + 1–2 smoke tests |
| **Small** | Local state, one module | Interface + CONTRACT comments + verify |
| **Medium** | Shared interface, multiple files | Spec + interface + CONTRACT + verify |
| **Large** | Trust boundary, multiple domains | Full spec + invariants + interface + verify + Plan + Reviewer pass |

> Scale = risk complexity. Slice size = delivery size (4–8 hrs, 3–7 AC). Do not confuse.

## Clarification Gate

### Micro / Small — Tripwire
Answer all three before proceeding:
1. Single observable outcome of this change?
2. Existing behavior that must not be affected?
3. How will we verify this worked?

### Medium / Large — Audited Two-Step

Evaluate: Goal / Non-goals / AC (verifiable yes/no each) / Edge cases / Invariants.

Score 0.0–1.0 per dimension with verbatim evidence (≥ 8 chars) or literal `none` (`none` → score ≤ 0.30). Proceed only when ambiguity ≤ 0.20 AND blocking_questions = 0.

**You cannot self-confirm. Three calls required:**

**1.** `draft_ambiguity_score(project_root, user_prompt_verbatim, goal_clarity, goal_evidence, constraint_clarity, constraint_evidence, success_criteria_clarity, success_evidence, blocking_questions)`

**2.** Dispatch auditor with returned `auditor_prompt_markdown`:

| CLI | Dispatch |
|---|---|
| Claude Code | `Task` tool, `subagent_type="general-purpose"`, `prompt=<auditor_prompt_markdown>` |
| Pi | `pi -p --no-tools "<auditor_prompt_markdown>"` |
| Codex | `codex exec "<auditor_prompt_markdown>"` |
| Gemini | `gemini -p "<auditor_prompt_markdown>"` |

**3.** `commit_ambiguity_audit(project_root, draft_id, auditor_transcript)` — transcript VERBATIM, never edited. Print returned `report_markdown` before continuing.

Audit catches: fabricated evidence quotes · forced readings (unrelated words mapped to a dimension) · inflated `none`-evidence scores · tampered transcripts (missing `audit_token` → rejected). Bypasses surface in `gates.jsonl`.

## Workflow

```
[0] Project Type       once per project
[1] Vertical Slicing   if feature too broad — see references/slicing.md
[2] Scale Triage       always
[3] Clarification Gate always
[4] Spec               Medium+ → docs/specs/<feature>.md
[5] Invariants         Small: CONTRACT comments / Large: docs/invariants/<domain>.md
[6] Interface          Small+ → signatures fixed before implementation; human finalizes
[7] Plan               Large required / Medium optional → PLAN.md; user approves before implementation
[8] Implement          always — follow H2, H4
[9] Reviewer Pass      Large only
[10] Verify Gate       always
```

## Contract Artifacts

| Scale | Spec | Invariants | Verification |
|---|---|---|---|
| Small | 1 paragraph | `CONTRACT:` comments | inline asserts or test |
| Medium | `docs/specs/<f>.md` | `CONTRACT:` comments | `verify.sh` |
| Large | `docs/specs/<f>.md` | `docs/invariants/<d>.md` | `verify.sh` |

Invariants: use "always"/"never", state enforcement location. Categories: Safety / Consistency / Boundary / Performance. See `references/architecture-patterns.md`.

## Implementation Rules

1. **Read-Only Contracts** — no modification without explicit user approval.
2. **Link Management** — report missing/stale links; do not silently rewrite.
3. **Stop on Ambiguity** — contract contradiction → stop and report.
4. **No Scope Creep** — implement only what AC defines.
5. **Verify Gate** — run `./verify.sh`. One failure = not done.

Post-implementation report:
```
Changes: [file]: [summary]
Verification: typecheck / tests / lint / manual — pass/fail
Links: complete / missing: [list]
Unresolved: [blockers]
```

## Verify Gate

- Done = all automatic checks pass AND all required manual checks confirmed or handed off.
- ui-heavy / mixed: `track_manual_checks(op="declare")` at implementation start; `run_verify(feature=...)` returns `overall: pending_manual` while items remain — blocks "done".
- On failure: call `analyze_verify_failure` before patching.

## Reviewer Pass (Large only)

Read diff only — no style, no redesign. Block if any of:
- Invariant violated / non-goals touched / contract artifacts modified without approval
- New security / performance / concurrency risk / missing required links

## Contract Change Protocol

Only when: requirements changed, contradiction found, or contract provably too strict.
1. Stop. Report reason + affected artifacts + tests needing update.
2. Wait for explicit approval. Only then update and resume.

## Failure Handling

1. Root cause first — no blind patching.
2. Invariant violated → revert/rethink; do not layer fixes.
3. After any fix, rerun full relevant verification set.
4. Failure suggests wrong contract → Contract Change Protocol.
5. Contract-sensitive failure → H4: root cause only, wait for approval.

## Anti-patterns

- ❌ Code before interface/contract is clear
- ❌ Modifying tests to make them pass
- ❌ Changing interfaces without human approval
- ❌ "Done" without running required verify steps
- ❌ Patching over invariant violation instead of fixing root cause
- ❌ Silently updating link blocks or contract artifacts
- ❌ Self-confirming ambiguity score — auditor dispatch is mandatory
- ❌ Editing auditor transcript before `commit_ambiguity_audit` — pass VERBATIM
- ❌ "Done" while `run_verify` returns `overall: pending_manual`
- ❌ Patch before human approves fix strategy (H4)

## Response Format

1. Scale judgment (Q0–Q3 result + explanation)
2. Clarification Gate — Medium+: print full Ambiguity Report
3. Applicable workflow steps for this scale
4. Execute each step, showing artifacts
5. Block on user input at every contract decision

## References

Load only when needed:
- `references/slicing.md` — vertical slice guide
- `references/spec-template.md` — spec template
- `references/platforms.md` — Roblox / Unity / Elixir / TS / Python
- `references/test-onboarding.md` — test infra from zero
- `references/links.md` — link management rules
- `references/project-types.md` — per-type Verify Gate detail
- `references/architecture-patterns.md` — invariant templates

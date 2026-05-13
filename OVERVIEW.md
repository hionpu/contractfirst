# How It Works, and How It Compares

> A reader's guide to the lowtech-tdd / contractfirst harness — what it does, how it does it, and how it stacks up against other AI-coding workflows.

* * *

## At a glance

This harness adds three things to your project:

1. **A skill prompt** (`.claude/SKILL.md` + references) — instructions the AI loads at session start that tell it how to work: scale triage, clarification gate, contract artefacts, verify gate.
2. **An MCP server** (5 tools) — a separate process the AI calls for verification, ambiguity scoring, link checks, failure classification, and manual-check tracking. The tools return structured verdicts (e.g. `proceed: false`, `patch_allowed: false`) that the AI is supposed to honour.
3. **Optional filesystem locks** on contract files (`chmod 444` on POSIX; ACLs on Windows) — the only layer that physically prevents writes.

You install with one curl line. The AI does the rest, calling the MCP tools when the workflow says to. A human owns the contract files. Verification logs and gate decisions land in `.lowtech-tdd/` under your project root.

## A note on what "enforcement" means here

Three different strengths in this document:

- **Hard enforcement** (only on filesystem-locked contract files): the OS refuses the write. Nothing the AI does can bypass it.
- **Structured verdicts** (what the MCP tools return): tools return e.g. `proceed: false` or `patch_allowed: false` with reasons. The AI is *supposed* to honour the verdict — and a compliant agent will — but the MCP layer cannot physically stop a non-compliant agent from ignoring the result and proceeding anyway. The win is that the AI's claim is now checkable: the tool output is on disk, the agent's behaviour can be audited against it.
- **Skill instructions** (prose in `SKILL.md`): rules the AI is told to follow. Same compliance assumption as any other AI-workflow framework.

The harness's bet is that **shifting decisions from "AI's private judgement" to "structured tool output the human can read"** is the highest-leverage move available short of running the AI in a fully sandboxed agent loop. The MCP tools are not magic; they are the cheapest way to make the AI's claims falsifiable.

* * *

## The problem

AI coding assistants are willing but not reliable. The same failure modes recur across models, vendors, and toolchains:

- "All tests passed" — when they didn't run, or didn't run all of them.
- "The spec is clear enough" — when it isn't, and the assistant proceeds to over-implement.
- A failing test gets edited to make it pass, instead of fixing the implementation.
- Contract documents (spec, invariant, interface) get quietly rewritten to fit the patch.
- A UI feature is reported "done" because `verify.sh` exited 0 — but the screen is broken, the focus is wrong, the animation stutters.
- Architectural rules ("the server never touches client GUI") drift across iterations.

Most AI-workflow frameworks treat these as a discipline problem: write better rules in markdown and hope the model follows. In practice, models drift back to default behavior the moment context gets long or pressure mounts. The longer the session, the worse the compliance.

This harness takes a different position: **the failures the AI is structurally bad at avoiding need to be enforced outside the AI's control loop.**

* * *

## The split

Every step of an AI coding session falls into one of two categories.

**Things prose can constrain.** Style preferences, naming conventions, what to ask before guessing. The AI is generally willing to follow these because there's no cost to compliance.

**Things prose cannot constrain.** Self-reported facts ("did tests pass?"), self-judged thresholds ("is the spec clear enough?"), self-approved exceptions ("may I edit this contract?"). The AI has a structural incentive to claim success here, and no markdown rule prevents that.

The harness uses three layers, one for each category:

| Layer | What it covers | Mechanism | Strength |
|---|---|---|---|
| **Skill** (markdown loaded at session start) | Prose-constrained behaviour: scale triage, vertical slicing, response format, anti-patterns, project-type detection, invariant categorization | The model reads it as part of system context | Compliance assumption |
| **MCP server** (5 tools, separate process) | Structurally-cheatable decisions: verification results, ambiguity scoring, link integrity, failure classification, manual-check ledger | The tool returns structured verdicts; the AI's claim about the result is now checkable against the tool's actual output (saved on disk under `.lowtech-tdd/`) | Auditable; compliance still assumed at the API boundary |
| **OS** (`chmod 444` on POSIX, ACLs on Windows) | Write-protection on contract files (`docs/specs/`, `docs/invariants/`) | Filesystem refuses the write regardless of what the AI tries | Hard enforcement |

The first layer is what every framework does. The second moves decisions from "AI's private judgement" to "tool output anyone can re-run." The third is the only layer that physically blocks.

* * *

## What the harness actually does

### The skill (`skill/SKILL.md` + `references/`)

Loaded at session start via `CLAUDE.md` (Claude Code, `@`-import) / `GEMINI.md` (Gemini CLI, `@`-import) / `AGENTS.md` (Codex CLI — plain-text directive only; Codex does not implement an `@`-import, so the installer writes a literal instruction telling the Codex agent to read `.claude/SKILL.md` and the `references/` directory before any code change). Concretely encodes:

- **Project type triage.** One-time detection (logic-heavy / ui-heavy / mixed), cached as a single line `<!-- lowtech-tdd: project_type=X -->` in the agent-instructions file. Zero cost on subsequent sessions.
- **Scale triage (Q0–Q3).** Four questions — touches shared interface, persists state, crosses trust boundary, 3+ concerns collaborating — produce Micro / Small / Medium / Large. Required artifacts scale with risk: a typo fix doesn't need a spec.
- **Vertical slicing.** When a feature is too big for one contract, decompose into 4–8h slices that each pass through automation end-to-end. Never horizontal (UI layer → backend layer → DB) because horizontal slices can't be verified until the last one merges.
- **The four-part contract.** Spec (what), Invariant (always/never), Interface (signatures), Test/Verify (how we'll know). Each part has a separate file with prescribed cross-links.
- **Invariant categorization.** Safety / Consistency / Boundary / Performance. Written in "always" / "never" form, with the enforcement point named ("server-side", "shared store", "client module").
- **Architecture patterns as boundary invariants.** MVC / MVVM / ECS / Flux / Hexagonal — each pattern's structural rules become first-class invariants the AI must satisfy.
- **Four human-skill-preservation rules (H1–H4).** What zones are human-owned, when a hand-code quota applies, when the human must explain the root cause, and when the AI must do root-cause-only and wait for approval.
- **Anti-patterns.** Six concrete failure modes flagged by name.

### The MCP server (5 tools)

Each tool returns a structured verdict. A compliant agent honours the verdict; in all cases the verdict (and the inputs that produced it) are written to disk so the human can re-run or audit.

| Tool | What it does | Failure mode it makes auditable |
|---|---|---|
| `run_verify` | Subprocess-execs `verify.sh` (or language defaults: npm / pytest / mypy / ruff). Returns exit codes, durations, per-step status, and a log path under `.lowtech-tdd/verify-<timestamp>.log`. With `feature=...`, consults the manual-check ledger and downgrades a green automatic run to `overall: pending_manual` while required items remain. | "All tests passed" with no run, or with manual checks skipped — now the log file either exists or it doesn't. |
| `score_ambiguity` | Computes ambiguity = 1 − Σ(score × weight) with fixed weights 0.40 / 0.30 / 0.30. Each per-dimension score must be accompanied by a verbatim quote from the user's request (≥ 8 chars), or the literal token `none` which forces the score to ≤ 0.30. Returns `proceed: bool` plus the report markdown the skill expects to print. | "The spec is clear enough" without evidence — the AI can't claim high clarity without producing a quote that the human can read and judge. |
| `verify_links` | Parses each spec's `## Links` section, resolves targets on disk, checks reciprocal back-links. Reports `missing` / `stale` / `orphaned`. Read-only. Folder layout configurable via `.lowtech-tdd/config.json`. | Cross-references rot silently when files move. |
| `analyze_verify_failure` | Classifies a failure as `contract_sensitive` or `routine` via layered signals: failed step, file paths in contract dirs, multi-framework structured markers (pytest, Jest/Vitest, RSpec, Go test, Rust, NUnit/xUnit, ExUnit). For `contract_sensitive`, returns `patch_allowed: false` with a reason. Returns `classification_signals` so the verdict is auditable. | AI patches a failing test instead of surfacing the root cause. With this tool, "patch_allowed: false" is in the response — the user can see it. |
| `track_manual_checks` | Per-feature ledger of manual verification items (declare / confirm / handoff). `run_verify(feature=...)` consults it. | "Done" reported on ui-heavy work while playtest items are still pending. |

Every gate decision appends one JSON line to `.lowtech-tdd/gates.jsonl`. After a session you can `grep` for "did `analyze_verify_failure` ever fire, and did the AI proceed with `patch_allowed: false`?" That's the audit hook the prose-only frameworks don't have.

### The OS layer

After install, the user marks contract files read-only. This is the only enforcement that is fully outside the AI's control loop.

**POSIX (macOS, Linux, WSL, Git Bash):**

```bash
chmod 444 docs/specs/*.md docs/invariants/*.md
```

**Windows (native PowerShell):** `chmod` is not a Windows primitive. Use either:

- The read-only attribute (lightweight, fine for solo use): `Set-ItemProperty docs/specs/*.md -Name IsReadOnly -Value $true`
- Or NTFS ACLs (stronger): `icacls docs\specs\*.md /deny "%USERNAME%:W"`
- Or run the workflow inside WSL where `chmod 444` works natively.

Note that Windows read-only attribute is advisory in some tools and a process running as Administrator can override it. If you need genuinely tamper-resistant contract files on Windows, ACLs or WSL are the realistic options. The repo currently assumes a POSIX-style environment for the install scripts (`install.sh` is Bash); Windows-native Codex users should treat the OS layer as "best-effort" rather than hard enforcement.

* * *

## A worked session

```
User: "Add a leaderboard endpoint that returns top 10 players by score."

[Skill loaded at session start. Project type cached as `logic-heavy`.]

AI runs Scale Triage Q0–Q3:
  Q0 shared interface? yes (public API)
  → Medium

AI runs Clarification Gate via score_ambiguity:
  goal_clarity: 0.9
    evidence: "top 10 players by score"        ← verbatim from user
  constraint_clarity: 0.2
    evidence: "none"                            ← user said nothing about tie-breaks, refresh rate
  success_criteria_clarity: 0.4
    evidence: "none"                            ← user said nothing about how to verify

  → ambiguity = 0.49, proceed: NO

AI asks clarifying questions: tie-break rule? refresh rate? response shape?
User answers. Second call:
  ambiguity = 0.12, proceed: YES.

Spec written. User reviews. chmod 444 applied.

AI calls run_verify (no feature flag — logic-heavy, no manual checks):
  overall: pass. Done.
```

For a ui-heavy project, the same session ends differently:

```
... (spec + implementation as above) ...

AI calls track_manual_checks(op="declare", checks=[
  {"id":"V1","description":"button alignment at 1920x1080"},
  {"id":"V2","description":"focus order on Tab key"},
  {"id":"V3","description":"5 min playtest, no jank"},
])

AI calls run_verify(feature="leaderboard-ui"):
  automatic_overall: pass
  overall: pending_manual
  → run_verify returns pending_manual; a compliant agent surfaces the checklist instead of reporting done.

User runs the manual checks. For each:
  track_manual_checks(op="confirm", check_id="V1", note="screenshot saved")

After V1, V2, V3 confirmed:
  run_verify(feature="leaderboard-ui") → overall: pass. Done.
```

* * *

## Comparison with other approaches

### vs. a bare session (no harness)

This is the baseline most developers actually use. CLAUDE.md exists, maybe has a few sentences. The AI improvises a workflow per turn.

- **What's missing:** Every failure mode above. The AI reports test results, judges its own clarity, edits failing tests, drifts the architecture, patches over invariants.
- **When it's enough:** One-off scripts. Throwaway prototypes. Cases where the cost of a bad outcome is low.
- **When it isn't:** Anything with persistent state, anything where you'll be back in three months trying to understand what the AI did.

### vs. plain CLAUDE.md / AGENTS.md rules (no MCP, no skill structure)

The natural step up: write your rules in markdown and trust the AI to follow.

- **What works:** Naming conventions, style, "ask before assuming." Anything the AI has no incentive to violate.
- **What doesn't:** Anything where the AI has an incentive to claim success — verification results, ambiguity judgements, patch authority on contract failures. Rules like "always run the tests" or "never modify the spec" have a 100% failure rate over a long session because there's no consequence to ignoring them.
- **The honest version of this approach** is: you're writing rules that get followed when convenient and dropped when the model is under context pressure.

### vs. [obra/superpowers](https://github.com/obra/superpowers)

A large, mature framework (high six-figure star count on GitHub as of mid-2026), MIT-licensed, with plugins for seven CLIs. Same problem space, opposite end of the enforcement axis.

| | superpowers | lowtech-tdd / contractfirst |
|---|---|---|
| **Enforcement** | Prose + skill activation. RED-GREEN-REFACTOR is "MANDATORY" in italics; no programmatic check verifies it. | Prose + 5 MCP tools that return checkable verdicts. AI cannot silently fake `run_verify` (logs are on disk), cannot inflate ambiguity without producing verbatim evidence quotes, cannot get `patch_allowed: true` on a contract-sensitive failure. The AI still has to *follow* the verdict — but the verdict is auditable, which the prose-only approach is not. |
| **Workflow breadth** | ✅ 14 skills covering brainstorm → plan → TDD → subagent dispatch → review → branch finish. Strong primitives: subagent-driven-development, git worktree integration. | Narrower. One skill + references; no subagent dispatch; no worktree workflow. |
| **TDD depth** | Comprehensive `test-driven-development` skill with red-flags list, rationalization counters, "delete and restart" rule. | Lighter — TDD is a destination, not a per-feature ceremony. |
| **Project-type awareness** | Same workflow regardless of project shape. | First-class logic-heavy / ui-heavy / mixed split; `track_manual_checks` exists specifically for ui-heavy. |
| **Contract model** | Design documents, planned tasks. No Invariant/Boundary distinction. | Spec / Invariant / Interface / Test as separate artefacts with categorized invariants (Safety / Consistency / Boundary / Performance) and `chmod 444` on the files. |
| **Architecture patterns** | Not modeled. | MVC / MVVM / ECS / Flux / Hexagonal → first-class boundary invariants. |
| **Audit trail** | None. After the session, you cannot tell which gates were hit or skipped. | `.lowtech-tdd/gates.jsonl` records every gate decision. |
| **CLI reach** | Claude Code, Codex, Factory Droid, Gemini, OpenCode, Cursor, GitHub Copilot CLI. | Claude Code, Codex, Gemini. |
| **Maturity** | Established, big community. | New, single developer. |

**The honest read:** superpowers is the most polished version of the "teach the AI a workflow" approach. It's better than this harness at choreographing a full SDLC and packaging that across CLIs. This harness is better at the specific question of *will the AI actually follow the workflow when it's inconvenient* — because the gates that matter are enforced by code, not by prose.

Which one fits depends on a single empirical question: when your AI says "tests pass" or "the spec is clear enough," do you trust the claim?

- If yes → superpowers gives you a broader, more mature workflow.
- If no → this harness's MCP layer is doing work that superpowers' prose-mandatory rules cannot.

For solo developers in ui-heavy domains (Roblox, Unity, WPF, mobile UI) — the audience the underlying [V5 guide](./AI%E1%84%8B%E1%85%AA%20TDD+BDD%20%E1%84%92%E1%85%A1%E1%84%80%E1%85%B5%20-%20Low%20Tech%20Dept%20V5.md) was written for — this harness's manual-check ledger and OS-level contract lock close gaps that superpowers leaves open.

For a team in a logic-heavy domain with strong existing test culture, superpowers' subagent dispatching and worktree integration is meaningfully ahead.

The two are not exclusive. A reasonable advanced setup is to **use both**: superpowers for workflow breadth, this harness for tool-verified checkpoints and the audit trail. The MCP layer is independent of any skill framework — the tools work the same whether the skill above them is `lowtech-tdd`, `superpowers`, or hand-rolled.

* * *

## When to use this harness

Strong fit:

- You work alone, or in a 1–3 person team, with AI doing most of the typing.
- Your project has state, shared interfaces, or trust boundaries — the kind of code where mistakes compound.
- You build for a platform where automated tests cannot fully verify behaviour: game engines (Roblox / Unity / Godot), desktop UI (WPF / Qt / Avalonia), mobile UI, anything visual.
- You've had AI claim "tests pass" when they didn't, or edit a failing test to make it green. You're past the point of trusting the model on this.
- You want your contract files (spec, invariant) to survive 3 months of AI iterations without quietly rotting.

Weak fit:

- One-off scripts and throwaway prototypes.
- Codebases where automated tests are already exhaustive and trusted (the gates duplicate what your CI already does).
- Teams that already use a heavier workflow framework — adding a second one is friction, not enforcement.

* * *

## What's NOT in scope

Honest limits:

- **Rule H2 (hand-code quota).** Honor system. No tool counts whether you typed the interface yourself.
- **Vertical slicing quality.** `references/slicing.md` is prose. No tool verifies that a proposed slice is actually playtestable.
- **Spec content quality.** `verify_links` checks the link graph; it doesn't judge whether the Acceptance Criteria are actually verifiable.
- **Subagent dispatch, worktree workflow, code review choreography.** Not modeled. If you want these, look at superpowers.
- **TDD as ceremony.** This harness treats TDD as a destination — graduated to over time — not a per-feature RED-GREEN-REFACTOR loop. If strict TDD is your hill, superpowers does it better.
- **Plan-mode automation for Large features.** Skill-driven only. No tool verifies a PLAN.md exists before implementation begins.

These are deliberate. Programmatic enforcement is expensive to build and easy to make annoying. The harness gates only the failure modes that are (a) common, (b) high-cost, and (c) cheaply checkable by code. The rest stays in the skill prompt where it belongs.

* * *

## Further reading

- [`README.md`](./README.md) — install and reference.
- [`skill/SKILL.md`](./skill/SKILL.md) — the loaded behaviour spec.
- [`skill/references/`](./skill/references/) — slicing guide, spec template, platform tool maps, project-type detail, architecture-pattern templates.
- [`mcp-server/README.md`](./mcp-server/README.md) — MCP tool reference with example payloads.
- [V5 guide (Korean)](./AI%E1%84%8B%E1%85%AA%20TDD+BDD%20%E1%84%92%E1%85%A1%E1%84%80%E1%85%B5%20-%20Low%20Tech%20Dept%20V5.md) — the original methodology this harness implements.

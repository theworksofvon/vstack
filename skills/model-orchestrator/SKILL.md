---
name: model-orchestrator
description: Run a long coding task as a relay of planner, implementer, and reviewer across different models or providers, with handoff packets, independent review, and a ledger of every stage. Use when the user wants Claude, Codex, or another model to plan, build, or review each other's work.
---

# Model Orchestrator

Needs a way to reach a second model. Two transports, chosen at the start:

- **T3 Code.** If `orchestrator_capabilities` answers, delegate every stage
  with `delegate_task` and read models from its live catalog. Details in
  [references/t3-code.md](references/t3-code.md).
- **CLI.** Otherwise `scripts/mo.py run-stage` shells out to `claude -p`,
  `codex exec`, or `opencode run`, whichever is installed. Details in
  [references/provider-adapters.md](references/provider-adapters.md). With
  no CLI either, hand the packet to the user to run and continue from what
  they paste back.

Both transports write the same **paper trail**: a packet per stage under
`.orchestrator/runs/<run-id>/task.md`, the model's answer beside it as
`last-message.md`, and one line per stage in `.orchestrator/ledger.jsonl`
with model, duration, and cost. `mo usage`, `mo report <task>`, and
`mo dashboard` read that ledger. It is normally git-ignored.

## The pipeline

`discover → plan → approve → implement → test → review → repair → verify`

Roles are `planner`, `implementer`, and `reviewer`. A **profile** in
`.orchestrator/config.toml` fixes which model plays each role; the shipped
ones are `claude`, `openai`, and `mixed` (default). Pick from what the user
said: "just use Claude" or "keep it in my Anthropic quota" means `claude`,
"OpenAI only" or "Codex" means `openai`, otherwise `mixed`. If the file is
missing, copy [config.example.toml](config.example.toml) into place. Resolve
the profile to concrete models, in T3 from the catalog and elsewhere with
`mo profiles`, and report the resolution before delegating anything. Never
hardcode a model in a prompt or packet.

For a small, well-defined change, one capable agent and a light review is
enough. Use the full pipeline for long-running or high-risk work.
Parallelize only independent discovery or review; serialize edits.

### 1. Discover

Inspect the repository and task context: baseline branch and status,
relevant files, existing tests, available transports. Record facts, not
guesses. If the task is underspecified, ask only the question that blocks
safe planning; otherwise state assumptions in the packet.

### 2. Plan

Give the planner only necessary context and ask for goal and non-goals,
current-state findings, proposed design, ordered file-level steps,
acceptance criteria, test strategy, risks, rollback notes, and open
questions. No product code changes in this stage.

### 3. Approve and hand off

Present a concise plan summary, assumptions, selected models, and the
cost-quality trade-off. Wait for approval when the plan changes scope,
architecture, public interfaces, data, or external state. Then write the
implementer packet per [references/handoff-protocol.md](references/handoff-protocol.md).

### 4. Implement

The implementer follows the approved plan, inspects before editing, makes
the smallest coherent change, preserves unrelated user work, and reports
every changed file and command. A lower-cost implementer is right only when
the plan and acceptance criteria are concrete.

### 5. Test

Narrowest relevant checks first, then broader ones proportional to risk.
Capture exact commands and results. Distinguish "not run", "blocked", and
"failed".

### 6. Review

Give the reviewer the approved plan, acceptance criteria, diff, test
results, and relevant context, never private reasoning. Ask for findings
ranked by severity with file and line evidence and concrete fixes, covering
correctness, regressions, security and privacy, maintainability, tests, and
scope drift.

### 7. Repair and verify

Actionable findings go back to the implementer; design-level issues go back
to the planner. Re-run tests and an independent review when changes are
material. `max_repair_cycles` in the config caps the loop; surface repeated
disagreement to the user.

## Operating rules

- The repository, branch, uncommitted changes, tool availability, and user
  constraints are shared state. Inspect them before assigning work.
- Role boundaries stay explicit: a planner plans, an implementer changes
  files, a reviewer diagnoses against acceptance criteria.
- Strong model for ambiguous architecture, lower-cost model for mechanical
  implementation, a different provider for review so it starts with fresh
  context. Escalate quality-sensitive work rather than optimizing cost.
- Implementation and review happen in separate contexts. In `mixed` that is
  a different provider. In a single-provider profile it is a different
  model, which is weaker independence; say so in the completion report.
- Packets carry conclusions, evidence, decisions, and artifacts. No secrets,
  credentials, private prompts, or unnecessary repository contents.
- Run tests and read the diff after implementation and after every repair.
  A review approval is not verification.
- Cost and tokens are `exact` only when the provider reported them,
  `estimated` when computed from a rate card, `unavailable` otherwise.
- The user decides scope changes, destructive operations, external
  messages, deployments, merges, and budget overruns. Pause there and only
  there.

## Completion report

Selected roles and models and why; completed stages; files changed; test
and review outcome; remaining risks; usage and cost with their status; and
the next user decision, if any. Do not claim cross-model execution happened
unless the ledger shows it.

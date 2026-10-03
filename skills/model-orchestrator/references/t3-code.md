# T3 Code transport

T3 Code is an agent harness that runs Claude Code, Codex, OpenCode, and
others as providers and exposes an MCP server to the agent in each thread.
From version 0.0.46 (Orchestrator V2) that server carries `delegate_task`:
start a child agent on any enabled provider and model, wait, get the result.
When it is present it replaces the CLI adapters: the child shows up in the
app's lineage view with model, status, and duration, runs under T3's
permission model, and can be cancelled. Tool names may carry a prefix such
as `mcp__t3-code__`; the semantics are the same.

## Detect

Call `orchestrator_capabilities`. It returns every provider instance, its
live model catalog, and two flags per provider: `canRunChildTask` and
`canRunCrossProviderChildTask`. A provider with constraints listed
("disabled", "executable not installed") is not available for delegation.
Some harnesses attach the server lazily, so an empty first scan is not
proof of absence: make one direct call by name before concluding. If the
tools are missing but `T3_ACP_MCP_NODE` is set, the same tools answer
through the shell (`acp-mcp-call orchestrator_capabilities '{}'`). Only
then fall back to the CLI transport in
[provider-adapters.md](provider-adapters.md).

The catalog lists what T3 knows about, not what the account can reach. A
first stage that fails with "model does not exist or you do not have access"
means pick the next model in the catalog and note the substitution in the
completion report.

## Resolve roles

Profiles still name roles, but the catalog is the source of truth for model
IDs. Map each role to a `providerInstanceId` and a `model` id taken from the
capabilities response, and report that resolution before delegating. The
alias table in `.orchestrator/config.toml` is a preference list, not a
guarantee: if an alias names a model the catalog lacks, pick the nearest
listed one and say so.

## Run a stage

1. Write the packet to `.orchestrator/runs/<run-id>/task.md` first, so the
   stage is on disk before it starts. Its role instructions name the
   forbidden actions; for a planner or reviewer that is "do not edit
   files", and the `interactionMode: "plan"` option on the call backs it.
2. Call `delegate_task` with the packet as the task text and
   `target: { providerInstanceId, model }`. Use `mode: "async"` for
   anything over a minute, keep the returned `taskId`, and poll
   `task_status` rather than blocking. Pass a stable `clientRequestId` so a
   retry does not spawn a second child.
3. Save the returned result to `.orchestrator/runs/<run-id>/last-message.md`.
4. Ledger it:

   ```bash
   mo record --task-id T-1 --stage review --role reviewer \
     --provider <providerInstanceId> --model <model> --run-id <run-id> \
     --input .orchestrator/runs/<run-id>/task.md \
     --output .orchestrator/runs/<run-id>/last-message.md \
     --duration <seconds>
   ```

   Add `--cost-usd`, `--input-tokens`, `--output-tokens` only when T3
   reported them; `mo` marks cost `unavailable` otherwise. Add `--failed`
   when the child did not complete.

T3 does not enforce role boundaries per child beyond the interaction mode;
check the diff after every planner or reviewer stage.

## What stays native

Same-provider fan-out that the harness already offers (Claude Code's own
subagents or Workflow tool, Codex's subagents) is fine for discovery and
parallel review when it supports the chosen model. Use `delegate_task` when
the stage crosses providers, needs a model the native tool cannot select,
or you want the child visible in T3's lineage view. Do not create top-level
threads for a stage; that is a separate conversation, not a child task.

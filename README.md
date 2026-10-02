# vstack

My personal stack of agent skills. Every skill here is one I actually use, taken
from other people's stacks or written from scratch, and adapted so the same
`SKILL.md` runs in Claude Code, Codex, opencode, and Cursor.

Inspired by [pstack](https://github.com/cursor/plugins/tree/main/pstack). Same
shape, different owner: this one is tuned for how I work, and it stays small.

## Layout

```
skills/        one directory per skill, SKILL.md inside; the only real copy
skills/UPSTREAM  which skills came from elsewhere, and at what commit
agents/        subagent definitions
docs/          guides and reference
automations/   scheduled or triggered workflows
```

## Install

Skills are symlinked into each harness's skill directory, so one edit lands
everywhere and updating is `git pull`.

```bash
git clone https://github.com/theworksofvon/vstack
cd vstack && ./install.sh
```

`install.sh` finds the repo from its own location, so clone it anywhere.
Re-run it after pulling a new skill; it is safe to run repeatedly. To add a
harness, add its skills directory to the list at the top of the script.

Claude Code can also load the repo as a plugin via `.claude-plugin/plugin.json`
without cloning, but that path covers Claude Code only.

## Skills

| skill | for |
|---|---|
| `test-audit` | gate new tests and sweep low-value or implementation-coupled ones |
| `code-audit` | cut dead paths, magic numbers, nesting, and bunched functions while holding behavior fixed |
| `codebase-design` | shared vocabulary for deep modules, seams, and interfaces |
| `pr-reviewer` | review-only pass for correctness, regression, and security defects |
| `gh-stack` | stacked branches and PRs |
| `model-orchestrator` | split long tasks across agents and model backends |
| `skill-forge` | create, move, or remove a skill and wire it into every harness |
| `system-audit` | find drift on the machine: unpushed work, duplicate clones, toolchain mismatch. Assumes a `~/src/<org>/<repo>` layout with Homebrew and mise |
| `writing-for-agents` | how to write documents an agent consumes |
| `grilling` | stress-test a plan by relentless questioning |
| `retro`, `teach`, `wait-what` | reflection and explanation helpers |

## Adding a skill

Run `/skill-forge create <name>` in any harness. It reads `writing-for-agents`
first, places the skill under `skills/`, and runs `install.sh` to link it
everywhere. Vendored skills get a line in `skills/UPSTREAM`.

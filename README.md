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

### As a plugin, without cloning

The repo is also a plugin marketplace. In Claude Code, or the desktop app's
Code tab:

```bash
claude plugin marketplace add theworksofvon/vstack
claude plugin install vstack@vstack        # every skill
claude plugin install demo-video@vstack    # only demo-video
```

Pick one of the two: `vstack` already holds `demo-video`.

### demo-video in Cowork and claude.ai

Cowork installs the plugin from the same marketplace: Customize > Plugins >
Add marketplace > `theworksofvon/vstack`. A Team or Enterprise owner can
give it to everyone under Organization settings > Plugins & skills > Sync
from GitHub, set to Installed by default.

For claude.ai chat, `uv run skills/demo-video/scripts/demo.py package`
writes `demo-video.zip`; upload it under Customize > Skills. There the agent
drives your browser with Claude in Chrome while your screen recorder films,
and the sandbox makes the video. An upload stops at 30 MB, so Cowork suits
longer walk-throughs.

## Skills

| skill | for |
|---|---|
| `test-audit` | gate new tests and sweep low-value or implementation-coupled ones |
| `code-audit` | cut dead paths, magic numbers, nesting, and bunched functions while holding behavior fixed |
| `codebase-design` | shared vocabulary for deep modules, seams, and interfaces |
| `pr-reviewer` | review-only pass for correctness, regression, and security defects |
| `pr-feedback` | act on a batch of PR review comments and report a decision per comment |
| `guided-review` | discuss a session from the local guided review app and record the verdicts and comments that you give it |
| `gh-stack` | stacked branches and PRs |
| `model-orchestrator` | relay a task through planner, implementer, and reviewer on different models, via T3 Code delegation or provider CLIs, with a ledger per stage |
| `skill-forge` | create, move, or remove a skill and wire it into every harness |
| `system-audit` | find drift on the machine: unpushed work, duplicate clones, toolchain mismatch. Assumes a Mac with Homebrew and repos under one source root; finds its own paths |
| `writing-for-agents` | how to write documents an agent consumes |
| `grilling` | stress-test a plan by relentless questioning |
| `demo-video` | narrated demo video of an app, with spring zooms and captions, in a stock voice or your own cloned one. Records itself in Claude Code; in Cowork and claude.ai it films your screen and finishes the video in the sandbox |
| `explain` | router: picks a format for "help me understand X" and hands off to one of the four below |
| `explain-ste` | prose in ASD-STE100 Simplified Technical English, with a dial to relax it |
| `explain-diagram` | Mermaid diagram, rendered to SVG or an HTML preview |
| `explain-html` | one self-contained interactive HTML page |
| `explain-video` | narrated Manim animation; needs `uv`, `ffmpeg`, and a narrator |
| `retro`, `teach`, `wait-what` | reflection and explanation helpers |

## Adding a skill

Run `/skill-forge create <name>` in any harness. It reads `writing-for-agents`
first, places the skill under `skills/`, and runs `install.sh` to link it
everywhere. Vendored skills get a line in `skills/UPSTREAM`.

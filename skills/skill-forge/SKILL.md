---
name: skill-forge
description: Create, move, or remove a skill and wire it into every harness at once. Use when the user wants a new skill, wants an existing one installed for Codex, opencode, or Cursor too, or asks why a skill shows up in one agent but not another.
---

A skill lives in one place and is symlinked into every harness. Getting the
plumbing right is mechanical; getting the writing right is not. This skill
covers the plumbing and hands the writing to `writing-for-agents`.

## The layout

```
<vstack>/skills/<name>/SKILL.md     ← the only real copy
~/.claude/skills/<name>             → symlink
~/.codex/skills/<name>              → symlink
~/.config/opencode/skills/<name>    → symlink
~/.cursor/skills/<name>             → symlink
```

`<vstack>` is wherever the repo is cloned. `install.sh` at the repo root
owns the list of harness directories; it is the single source of truth for
where links go. A skill that exists in the repo but is missing a symlink is
invisible to that harness. This is the usual cause of "it works in Claude
but not Codex".

Find the repo from any harness: `readlink ~/.claude/skills/skill-forge`
prints the path to this skill, and the repo is two directories up.

## Creating one

1. **Write it first.** Read `writing-for-agents` and follow it, including its
   portability section. That skill owns how the document should read. The
   frontmatter `description` is what decides whether the skill ever fires,
   and it has rules.

2. **Place it** at `skills/<name>/SKILL.md`. Use a kebab-case directory
   name matching the frontmatter `name`.

3. **Link it** by running `./install.sh` from the repo root. It links every
   skill into every harness and prints a count per harness. Re-running it is
   harmless.

4. **Optionally add `agents/openai.yaml`** beside `SKILL.md`. Codex uses it
   only for a display name and short description in its skill picker; the
   skill loads without it.

5. **Commit the repo.** The symlinks are machine state; the skill is not.
   Only the repo belongs in git.

## Removing one

Remove the symlinks first, then the source. The reverse order leaves broken
links that fail silently:

```bash
NAME=<name>
for t in ~/.claude/skills ~/.codex/skills ~/.config/opencode/skills ~/.cursor/skills; do
  rm -f "$t/$NAME"
done
rm -rf "$(readlink ~/.claude/skills/skill-forge)/../$NAME"
```

## Vendored skills

`skills/UPSTREAM` records which skills came from someone else's repo and
at what commit. When adding a vendored skill, add a line there. When one has
been edited locally, say so in that file, otherwise the next sync silently
overwrites the local change.

## Auditing the wiring

`./install.sh` prints how many skills each harness sees. If the counts
differ, or differ from the number of directories under `skills/`, something
is unlinked or a non-symlink file is squatting on the name; the script
reports those as `SKIP` lines.

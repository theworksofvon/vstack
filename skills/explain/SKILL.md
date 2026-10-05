---
name: explain
description: Explain a topic in the format that fits the question. Use when the user asks to understand, explain, walk through, visualize, or diagram how something works. Routes to STE prose, a Mermaid diagram, an interactive HTML page, or a narrated video.
---

Pick a format, say which in one line, then follow that format's skill. The
four format skills sit beside this one; read the chosen one at
`<this skill's directory>/../explain-<format>/SKILL.md` and continue from
its first step. If the user named a format, skip the table.

| the question is about | format | skill |
|---|---|---|
| what a thing is, a definition, a difference between two things | prose | `explain-ste` |
| a process, lifecycle, sequence of calls, or how parts relate | diagram | `explain-diagram` |
| behaviour that changes with a parameter, a trade-off worth feeling, an algorithm worth stepping through | page | `explain-html` |
| a build-up over several ideas that needs motion to land | video | `explain-video` |

When two rows fit, take the cheaper one (prose, then diagram, then page,
then video) and name the next one up as an option. Learning a topic over
many sessions is `teach`, not this.

## The brief

Every format opens the same way. Do this before touching the format's steps:

1. **One question.** Write the single question the reader has, in their
   words. If the request holds two, pick the one they asked first and name
   the other as a follow-up.
2. **Three to five ideas.** List the ideas that, once held, answer the
   question. Fewer than three and the format is overkill; more than five and
   the explanation needs splitting.
3. **A slug.** Kebab-case, from the question, under forty characters:
   "how do Kafka consumer groups rebalance" becomes
   `kafka-consumer-rebalance`.

Files go in `${XDG_CACHE_HOME:-$HOME/.cache}/vstack/explain/<slug>/`, never
in the current repo. Create the directory, write there, and end by printing
the path of the main artifact.

## Shared reference

- [`STE100.md`](STE100.md): the ASD-STE100 rule digest. `explain-ste` and
  `wait-what` both write to it.

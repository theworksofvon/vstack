# One agent per scene

You are the lead. You do steps 1 to 4 of `SKILL.md` alone, because every
scene depends on them. Then the scenes go to subagents, and you do steps 7
to 9.

## What the lead writes first

- `narration/NN.txt` for every scene, and the `narrate` run.
- `common.py` in the work folder: the app URL, and each helper that 2
  scenes need (a row locator, a count reader). Leave `scenes.py` as it is.
- `brief.md` in the work folder: the slug, the mode, the rehearsal notes
  for each scene (selectors, waits), and the chains below.

## Chains

A **chain** is a run of scenes where one needs the data that another
made: scene 02 sends the asset that scene 01 created. Scenes in a chain
record in order, so 1 chain goes to 1 agent, or the lead records it.

A scene with its own data is a chain of 1. Make more of these when it is
cheap: seed 1 record per scene before the agents start, so no scene waits
for another. Do this only when the screen then still tells 1 story; a
counter that shows 40 in one scene and 12 in the next is a fault.

## The brief for each subagent

Give each one this, with the values in:

> Read `<skill directory>/SKILL.md`: the sections Scene shape, Scene API
> and the rules under it. Read `<work folder>/brief.md` and
> `narration/NN.txt`.
> Write `<work folder>/scene_NN.py`: `from kit import scene`, helpers from
> `common.py`. Change no other file.
> Record with `demo record <slug> NN`. Read `shots/NN.png` and 3 frames of
> `frames/NN/`. Done when the last frame shows the result that the last
> narration line names.
> Report: the scene length that `record` printed, each selector that the
> brief had wrong, and each thing on screen that the narration does not
> say.

An agent that owns a chain gets every `NN` of the chain and records them
in order.

## After the agents

1. Record again, in 1 run, each chain whose scenes ran in separate
   browsers and must look continuous.
2. Read every `shots/NN.png`. Send back a scene whose result is not on
   screen.
3. Go on with step 7 of `SKILL.md`.

---
name: explain-video
description: Explain a topic as a short narrated animation in the 3Blue1Brown style, built with Manim and ffmpeg.
disable-model-invocation: true
argument-hint: "<topic>"
---

Needs `uv` and `ffmpeg` on PATH, plus one narrator from
[`NARRATION.md`](NARRATION.md); macOS `say` counts. Manim, the animation
library, is fetched by `uv` per run, so nothing is installed globally. The
first run downloads it and takes a minute. LaTeX is not assumed: draw
formulas with `Text` and `MarkupText`, never `MathTex` or `Tex`.

A video costs ten times a page. Keep it to two to four scenes and under
ninety seconds; past that, split the topic.

1. Run the brief from [`../explain/SKILL.md`](../explain/SKILL.md): one
   question, three to five ideas, a slug. Each idea becomes one scene.
2. Write `script.md` in the slug directory: for each scene, the narration
   (three sentences at most, in the 80% rules of
   [`../explain/STE100.md`](../explain/STE100.md)) and one line saying what
   is on screen while it is read. Narration leads; the picture shows what
   the words name, as the words name it.
3. Narrate first, so the picture can be timed to the words. Save each
   scene's narration to `narration/NN.txt` and produce audio per
   [`NARRATION.md`](NARRATION.md). Measure each duration:
   `ffprobe -v error -show_entries format=duration -of csv=p=0 narration/NN.aiff`.
4. Write `scenes.py`: one `Scene` subclass per scene, named `S01`, `S02`,
   and so on. Rules that keep the output clean:
   - total animation time per scene within its narration's duration; the
     assembler holds the last frame if narration runs longer;
   - one new object per sentence of narration, introduced as the sentence
     would land, with `run_time` set to fit;
   - a dark background, two or three colours, text at `font_size=36` or
     larger, so it reads at phone size;
   - `self.wait(0.5)` as the last line, so the cut is not abrupt.
5. Render every scene at medium quality:
   `uv run --python 3.12 --with manim manim -qm scenes.py S01 S02 ...`.
   Fix any Python error and re-render only the failing scene.
6. Assemble: `uv run <this skill's directory>/assemble.py <slug directory>`.
   It pairs each scene with its narration, pads the shorter of the two, and
   writes `final.mp4`. Open it with `open` or `xdg-open`. A playable file
   whose narration matches the picture is the completion criterion; watch
   at least the first scene, or if the harness cannot, check that
   `ffprobe` reports one video and one audio stream of equal length.
7. Print the path, the narrator tier used, and the scene list.

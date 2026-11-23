---
name: demo-video
description: Make a narrated demo video of an app, with click sounds, spring zooms and captions, in a stock voice or the user's own. Use when the user asks for a demo video, product video, walkthrough recording, or screen recording of an app or feature.
compatibility: Claude Code, in a terminal or the desktop app's Code tab, records a web app itself; it needs uv and sets up the rest. Cowork, claude.ai and the desktop app film the user's screen with its own recorder while Claude in Chrome or computer use drives the app, then finish the video in the sandbox with pip packages.
---

Every command is `demo <command>`: `uv run <this skill's directory>/scripts/demo.py`,
or `python <this skill's directory>/scripts/demo.py` where there is no `uv`
(first `pip install numpy soundfile pillow imageio-ffmpeg`). `demo --help`
lists the commands.

The user can be someone who does not code, in the desktop app's Code tab.
On a Mac or Linux machine without `uv`, tell them in 1 sentence that you
will install a free tool that runs the video scripts, then run
`curl -LsSf https://astral.sh/uv/install.sh | sh` and use
`~/.local/bin/uv`. The first run downloads Chromium and the voice model
by itself; say that it takes a few minutes. The work folder is
`${XDG_CACHE_HOME:-$HOME/.cache}/vstack/demo-video/<slug>/`, never the repo.

## Path

Run `demo doctor <app url>` first. Its last line names the path:

- `path: record`: this machine drives a browser on the app. Follow the
  steps below.
- `path: screen`: the browser here cannot reach the user's app (a claude.ai
  or Cowork sandbox), or the app is a native app. Read
  [`SCREEN.md`](SCREEN.md) and follow it in place of the steps below; it
  uses the Mode, Narration and Voice sections of this file.

## Mode

Take the mode from the request; when it names none, use `demo`.

| mode      | for                                         | rules                                                                                                                            |
| --------- | ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `demo`    | showing a feature to people who will use it | no hook, no sales lines; narration says what the screen does; real speed, only dead time is cut                                  |
| `product` | selling it                                  | 1 problem card first, 1 closing card, narration names the benefit; action sped up to the narration's length, about 90 s in total |

A `launch` film (large moving text, the UI only as proof) is not built here.
The measured videos behind these rules are in [`REFERENCE.md`](REFERENCE.md);
read it when you set a length or a pace.

## Steps

1. **Brief.** Write the 1 thing the viewer must believe at the end, then
   3 to 6 scenes that prove it, each 1 action the viewer can follow. Pick a
   kebab-case slug. Run `demo init <slug>`.
2. **Get the app running and signed in.** Start it the way the project
   says. Services the app needs but the machine lacks get a local stand-in
   outside the repo; say so in the final report. If the app has a sign-in,
   run `demo login <slug> <url>` in the background. It first tries the
   saved sign-in of that app without a window. When it opens a window,
   tell the user: find the window titled **SIGN IN HERE (demo-video)**,
   not their own Chrome; sign in there; click **Accept** if an "Authorize
   App" screen shows. It prints each page the window reaches, so read its
   output to say where a sign-in stopped.
   Done when a plain page load of the app shows data.
3. **Narration first.** Write `narration/NN.txt` per scene and card by
   [the narration rules](#narration). Run `demo narrate <slug>`; it prints
   each length. The picture is timed to these lengths.
4. **Rehearse by hand.** Before any scene code, walk the full flow once
   with a browser tool or a headed run, and write down for each scene the
   selector of each element and how long each wait is. Seed or reset data
   so a second take starts from the same state. A scene written from a
   guess fails mid-take and costs a full re-record.
5. **Write `scenes.py`** from the template `init` made, using
   [the scene API](#scene-api), each scene in [the scene shape](#scene-shape).
   One scene per narration file, same number. A scene can also live in its
   own `scene_NN.py` beside `scenes.py`; `record` loads both.
   After the edit step, set each `[pause N]` so a line starts when its
   beat starts; `edit` prints the lengths, and `frames/NN/cut.json` has the
   click and camera times.
6. **Record.** `demo record <slug>`, or `demo record <slug> 03` for 1
   scene. After each scene, read `shots/last.png` and 3 frames from
   `frames/NN/`; a scene is done when its last frame shows the state the
   narration names.
7. **Edit.** `demo edit <slug> --mode <mode>`. It prints each scene's
   length against its narration.
8. **Build and check.** `demo build <slug>`, then `demo check <slug>`.
   Check must print `PASS`: it fails on more than 3 flashes in 1 second, on
   a cut through black, and on sound and picture of different length. Then
   read the `final.sheet.jpg` it wrote; every scene must show what its
   narration says. Fix and rebuild until both hold.
9. **Report** the path of `final.mp4`, its length, the mode, the narrator
   used, what was a stand-in, and anything visible that the user did not
   ask for (a real name, an error row).

When you can start subagents and the demo has 3 scenes or more, read
[`PARALLEL.md`](PARALLEL.md) after step 4: it gives each scene to 1 agent.

## Scene shape

A scene is 1 idea, told in 5 beats. Each beat has 1 narration line, with a
pause after it.

| beat   | on screen                                                | tool                          |
| ------ | -------------------------------------------------------- | ----------------------------- |
| orient | the full page, still, for 1 s; the caption says the idea | caption of `@scene`, `d.wait` |
| point  | the camera goes to the thing the viewer must watch       | `d.ring(zoom=)` or `d.focus`  |
| act    | the click or the text, at a speed a person can follow    | `d.click`, `d.type`           |
| result | the thing that changed, marked                           | `d.ring` with a label         |
| hold   | the full page again, still                               | the tool adds this            |

Fixed, because the viewer needs it:

- The scene starts from a known state, set inside `d.cut()`.
- The last frame shows the result that the last narration line names.
- A ring label has 5 words at most and names what changed, not what to do.
- 1 main action. 2 or 3 are right only when they are 1 idea ("confirm
  one, or confirm a group").

Yours to choose: the zoom level, which element proves the result, how many
point and result beats a scene repeats, where a `d.notice` or a
fast-forward helps, and the caption words. When the app has a better way
to show the idea than these beats, use it and keep the 4 fixed rules.

## Scene API

`d` is the demo; `d.page` is the Playwright page for any locator or wait.

```python
from kit import card, scene, skip

card(
    "00",
    kicker="Product",
    title="The problem in <em>1 line</em>.",
    sub="...",
    seconds=5,
)


@scene("01", "Caption shown for the first 3 seconds")
def create(d):
    d.goto(APP)
    button = d.page.get_by_role("button", name="New asset")
    d.ring(button, zoom=1.3)  # ring, camera moves in
    d.click(button)  # cursor glides, ripple, click sound
    d.focus(d.page.get_by_role("dialog"), zoom=1.2)
    d.type("Greater Duchess")  # key sounds; types into the focused element
    with d.cut():  # this wait is not in the video
        d.page.get_by_text("Parsed").wait_for(timeout=600_000)
    with d.fast_forward("Remaining fields · 10× speed"):
        for row in rows:
            d.click(row)  # plays 10x, label on screen
    d.wide()  # camera back to the full page
```

Also: `d.wait(s)`, `d.until(video_seconds)`, `d.point(el)`, `d.notice(title,
detail)`, `d.shot(name)`, `skip("reason")` to drop a scene that cannot run.

Rules the tool cannot enforce:

- **The page stays as designed.** Zoom only with `d.focus` and `d.ring(zoom=)`:
  they write a camera note and the build crops the frames. Never scale,
  restyle or resize the app from a scene.
- **Zoom stops at 1.67x** at the default `--scale 2`; record with
  `--scale 3` for up to 2.5x.
- **After a click that opens a dialog, `d.focus` the dialog** in the next
  line, so the camera goes with it.
- **A long wait is a `d.cut()`; a long repeat is a `d.fast_forward()`.**
  Never leave either at real speed.

## Narration

Write for the ear: the text is heard once, at the speed of speech.

- **1 idea per sentence, 12 words at most**, in the words a user of the app
  says. Say what the viewer sees now: "Stamp the field", then the result.
- **Read it aloud once.** Rewrite each place where the tongue trips or a
  breath runs out.
- **Pauses are part of the text.** An empty line is 0.5 s; `[pause 1.2]` is
  1.2 s. Put one before each new step and after each result, so the voice
  waits for the screen.
- **Too long? Cut words.** Keep `--speed` at 1.0; a faster voice sounds
  pressed.
- **Words the voice says wrong** go in `narration/pronounce.json`, as
  `{"MI": "M I", "PFS": "P F S"}`. Listen for product names, short forms and
  place names, then run `narrate` again.

## Voice

`demo narrate <slug>` reads each `narration/NN.txt` to `NN.wav`. Ask the
user which voice they want before the first `narrate`:

| voice                              | how                                                                                                                                                                                | where it runs                                                                                             |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| a stock voice (default `af_heart`) | `--voice <name>`; `demo voices` writes 1 sample per voice, American and British, women and men, to offer                                                                           | everywhere: Kokoro, a local model, free                                                                   |
| the user's own, cloned             | 1 time: `demo clone record` films 15 s from the microphone while the user reads the passage it prints, or `demo clone <file>` takes a recording of that passage. Then `--voice me` | Claude Code on a Mac with Apple silicon: Qwen3-TTS, local, free, no account; the first run downloads 2 GB |
| the user reads it                  | the user records each scene's text; save each take as `narration/NN.m4a` (or `.wav`, `.mp3`), and skip `narrate`                                                                   | everywhere                                                                                                |

A cloned voice is the user's own only: clone no one else's. Say in the
final report that the narration is an AI voice. Tone comes from the voice
and the text; neither model has a control for emotion.

Sound finish, done by `build`: the level is set to -18 LUFS. A file named
`music.mp3`, `music.wav` or `music.m4a` in the work folder plays under the
voice and goes down while the voice speaks; add one only when the user
gives it.

## Changing a take without a new recording

`frames/NN/manifest.json` is the recording: frame times, sound cues and the
`camera` list (`t`, `cx`, `cy` in page pixels, `z` zoom, `d` seconds until the spring is 96% there). Edit a
camera entry to move, retime or remove a zoom, then run `edit`, `build` and
`check` again. Old takes move to `frames-old/`.

`demo selftest` runs the full flow on a built-in page; run it first when a
command fails, to tell a tool fault from a scene fault.

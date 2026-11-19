# The screen path

You drive the app on the user's computer, the user's own screen recorder
films it, and this sandbox makes the video from that file. Use Claude in
Chrome for a web app and computer use for a native app; computer use cannot
click inside a browser.

With neither tool (the claude.ai website), the user clicks and you direct.
Before each scene, tell the user the scene's actions in 1 short list and
ask them to reply `next` when they are ready. Run `demo mark` when the
reply comes, then they act. Their own mouse is in the video, so skip
`demo overlay`.

## What this path cannot film

Tell the user before step 1 when the request hits one of these:

- **A native app without computer use.** Computer use is in the Pro, Max
  and Ultra plans only, not Team or Enterprise, and Claude Code in a
  terminal has none. Offer a web app, or let the user click while you mark
  the scenes.
- **Typing in a terminal or an IDE.** Computer use can click there but not
  type. A CLI tool is better shown in a web terminal, or not at all.
- **A recording over 30 MB in claude.ai or desktop chat.** That is about 2
  minutes of a full screen. Cowork reads the file from the attached folder
  and has no limit.

## Steps

1. **Brief, mode, narration.** Step 1 of `SKILL.md`, the Mode table, then
   `narration/NN.txt` per scene by the Narration section. Ask which voice
   (the Voice section), and run `demo narrate <slug>` unless the user reads
   it. No cards: the screen path films only the app.
2. **Where the file goes.** In Cowork, ask the user to attach the folder the
   recorder saves to (the Desktop on a Mac). In claude.ai or desktop chat,
   the user uploads the file after step 5, and an upload stops at 30 MB:
   ask for a short walk-through, 2 minutes at most.
3. **Set the screen.** Open the app at the first scene's page and make the
   browser window fill the screen. Close what must not be filmed: mail,
   chat, other tabs. The video is cut to 16:9 from the middle of the screen.
   In a web app, run the output of `demo overlay` with Claude in Chrome's
   JavaScript tool. Claude in Chrome does not move the real mouse, so
   without it the video shows no pointer. Run it again after each page
   load: a new page drops it. A native app needs none: computer use moves
   the real mouse.
4. **Start the recorder, then mark.**
   - With computer use: request access to the Screenshot app on a Mac,
     press Cmd+Shift+5, choose Record Entire Screen, click Record.
   - Without it: ask the user to do the same (on Windows, Win+Alt+R) and
     to tell you when it records.

   Then run `demo mark <slug> start`.

5. **Walk through, 1 scene at a time.** Run
   `demo mark <slug> NN "caption"` before the first action of each scene,
   then do the scene's actions. Each wait while you think is cut to a short
   pause later, so take the time you need. In a web app, click with the
   JavaScript tool, `await __demo.click("<css selector>")`: the drawn
   cursor glides to the element like a hand, then clicks when it lands. A
   click from Claude in Chrome's own tool jumps: the page changes first and
   the cursor follows. Use that tool only where the page needs a real click
   (a file picker, a drag), after `await __demo.point("<css selector>")`
   moves the cursor there. Type with Claude in Chrome as usual. A scene is done when the screen
   shows the result its narration names.
6. **Stop the recorder.** With computer use press Cmd+Ctrl+Esc; else ask
   the user to click Stop in the menu bar. Get the file: from the attached
   folder, or ask for the upload.
7. **Finish.** `demo finish <slug> <file>`, then `demo edit <slug>`,
   `demo build <slug>` and `demo check <slug>`. `finish` prints the
   actions and zooms per scene. When a scene has no frames or its cut is
   wrong, run `finish` again with `--offset <s>`: the seconds into the
   recording at which the `start` mark falls.
8. **Look and deliver.** Step 8 and 9 of `SKILL.md`: `check` must print
   `PASS`, and `final.sheet.jpg` must show each scene's result. Put
   `final.mp4` where the user gets it: the attached folder, or the outputs
   folder of the chat.

## What finish does

It keeps only the frames that change, so a blinking caret and the time you
spent thinking do not count. Each still gap becomes a pause that grows to
fit the narration, up to 3 s. Each burst of change gets a click sound; a
burst that changes a small area gets a spring zoom on it, and the camera
goes wide again on a large change or at the end of the scene. To move or
remove a zoom, edit `frames/NN/manifest.json` and run `edit` and `build`
again.

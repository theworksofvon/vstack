---
name: explain-html
description: Explain a topic as one self-contained, interactive HTML page opened in the browser.
disable-model-invocation: true
argument-hint: "<topic>"
---

Needs nothing beyond a browser: the page opens with `open` on macOS or
`xdg-open` elsewhere.

1. Run the brief from [`../explain/SKILL.md`](../explain/SKILL.md): one
   question, three to five ideas, a slug.
2. Choose **one** interactive element. It is the reason this is a page and
   not prose: a slider that changes a parameter and redraws, a stepper that
   walks an algorithm one move at a time, a toggle that shows two designs
   side by side. The widget must make one of the ideas visible as it moves.
   Everything else on the page is static.
3. Write `index.html` in the slug directory. One file, inline CSS and JS,
   no network requests, so it opens offline and survives a copy. Structure:
   - the question as the title;
   - one section per idea, in reading order, each under 120 words;
   - the widget inside the section whose idea it shows;
   - a closing section, "so what", that says what the reader can now do.
   Typography is the whole design: a system font stack, a reading column of
   about 70 characters, generous line height, and colours that honour
   `prefers-color-scheme`. Code samples sit in `<pre>` with horizontal
   scroll. A chart or plot on the page follows the `dataviz` skill when the
   harness has it.
4. Open the file in the browser. Then reload the page yourself with a
   headless check when one is available (a browser tool, or
   `node -e` over the file) and fix any console error. A page that renders
   without errors and whose widget responds is the completion criterion.
5. Print the file path and one line per idea, so the chat holds a summary
   when the page is gone.

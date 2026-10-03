---
name: explain-diagram
description: Explain a process, flow, or structure as a Mermaid diagram, rendered to SVG or an HTML preview.
disable-model-invocation: true
argument-hint: "<topic>"
---

Needs nothing. Renders to SVG when the Mermaid CLI `mmdc` is on PATH;
otherwise writes an HTML preview that loads Mermaid from a CDN, so the
fallback needs network once.

1. Run the brief from [`../explain/SKILL.md`](../explain/SKILL.md): one
   question, three to five ideas, a slug.
2. Pick the diagram type from the question. One diagram per question; a
   second question gets a second file.

   | the question asks | type |
   |---|---|
   | what happens, in what order, with what decisions | `flowchart TD` |
   | who talks to whom, over time | `sequenceDiagram` |
   | what states a thing passes through | `stateDiagram-v2` |
   | how parts are composed or related | `classDiagram` or `erDiagram` |
   | how work overlaps in time | `gantt` |

3. Write `diagram.mmd` in the slug directory. Rules that keep it legible:
   - twelve nodes at most; past that, split by idea into two diagrams;
   - every edge labelled with a verb phrase, so the arrow carries meaning;
   - node text under six words, with the idea's defining term in it;
   - one `subgraph` per idea from the brief when the type supports it;
   - no styling directives until the structure is right.
4. Render. With `mmdc`: `mmdc -i diagram.mmd -o diagram.svg -b transparent`.
   Without it, write `index.html` beside the source containing a `<pre
   class="mermaid">` block with the diagram and a `<script type="module">`
   that imports Mermaid from `https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs`
   and calls `mermaid.initialize({ startOnLoad: true })`. Open whichever
   file resulted with `open` or `xdg-open`.
5. If rendering reports a parse error, fix the source and render again. A
   rendered image is the completion criterion.
6. Print the file path and the Mermaid source in a fenced `mermaid` block,
   so the diagram survives in chat and in any viewer that renders Mermaid.

# FHDIC deck (HAC-86: web deck)

The submission deck is a web page served by the demo app at **`/deck`**
(<https://supermomo668--daypart-demo-playground.us-east.modal.run/deck>). It uses the member app's
tokens (dark navy, Inter, periwinkle and teal accents) and reads top-down:

| slides | section | what |
|---|---|---|
| 1–2 | Problem | who it is for, what fails today, why a record you can see, correct and act on matters |
| 3–5 | Design | the member flow (check-in → review → passport → Inclinations → next step → a person), with real screens |
| 6–9 | Technical solution | architecture, memory and the honesty layer, question library + reward model + GRPO, results |
| 10 | Next | next steps, the demo, the deck and the repo |

Navigation: ←/→, Space, PageUp/PageDown, Home/End, the section tabs, the arrow buttons, a click on the
slide, and `#/<n>` deep links. **N** opens the speaker notes. At phone width the slides reflow into one
scrolling column, and the wide diagrams scroll sideways.

**Still true.** Every number on a slide comes from an [evidence-ledger](../evidence-ledger.md) row.
Each slide and each figure names its rows in a `data-ledger` attribute, and the speaker notes name them
again. The charts are drawn from the `DATA` table in `build_web_deck.py`, keyed by ledger row, so a chart
cannot drift from the ledger. Per-trait recovery values (slide 8) are row L75's, read from
`docs/daypart/results/metrics.json`. The visual deck carries no caveat labels (HAC-86). The ledger, the
appendix and the form answers keep them unchanged.

| file | what |
|---|---|
| `build_web_deck.py` | the slide spec. It writes `engine/daypart/demo/deck/index.html` and copies `screens/` next to it (standard library only). |
| `engine/daypart/demo/deck/deck.css`, `deck.js` | the style and the navigation, hand-written |
| `export_deck.py` | prints `/deck?export=1` to the PDF and renders `slide-N.png` (1600×900) for the video |
| `clinical-human-clone-deck.pdf` | the form PDF: 10 pages at 1600×900, 1.04 MB (limit 5 MB), tagged, live links to the demo, the deck and the repo |
| `screens/*.jpg` | crops of real screenshots of the hosted build (`daypart/build` 4ba3adb, 2026-11-11) |

**No PPTX.** The deck is HTML and SVG now. An editable PPTX would mean redrawing every figure as shapes,
so the form gets the PDF and the hosted page instead. The HAC-77 PPTX and its builder were removed.

Rebuild (from the repo root):

```sh
python docs/daypart/submission/deck/build_web_deck.py
# serve the app (e.g. `cd engine && uv run daypart-demo`, or use the hosted URL), then:
python docs/daypart/submission/deck/export_deck.py <base_url> --png <slides_dir>   # needs the engine `ui` group
```

Tests: `engine/tests/unit/test_deck_unit.py` covers the route, the sections, the ledger rows, the absent
caveat labels and the word budget. `engine/tests/ui/test_deck_ui.py` covers keyboard, click and hash
navigation, axe at 1280 and 375, and the 1600×900 export.

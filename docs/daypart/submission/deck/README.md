# FHDIC deck (HAC-65)

**Template pending.** The organiser's official template is not public (HAC-63; ledger P1), so this
deck uses a plain, accessible layout and says "Template pending" on every slide. It claims no
template compliance. When a person with the dashboard login has the template, move the 8 slides
into it. The editable PPTX holds every text as a native text box and every diagram as shapes, so
the move is copy and paste.

| file | what |
|---|---|
| `clinical-human-clone-deck.pptx` | editable deck, 8 slides, 16:9. The speaker notes name the ledger rows behind each slide. |
| `clinical-human-clone-deck.pdf` | the same 8 slides as a PDF: 0.67 MB (limit 5 MB), tagged, 2 live links |
| `screens/*.jpg` | crops of real screenshots of the hosted build (`daypart/build` e50ebb7, 2026-11-10) |
| `build_deck.py` | the one slide spec. It writes the PPTX and `deck.html`. |
| `deck_pdf.js` | prints `deck.html` to the PDF and renders slide PNGs (`DSF=1.25` gives 1600×900 for the video) |

Source: [deck outline](../deck-outline.md) and [evidence ledger](../evidence-ledger.md). Every
number on a slide comes from a ledger row named in that slide's notes. The rules from the outline,
as applied:

- One message per slide, as the outline's slide title and message. Body type is at least 12.5 pt
  and titles 34 pt. Ink `#111318` on white, and no text colour below 7:1 contrast.
- Footer on every slide: "Synthetic / simulated results · Synthetic data only · Not medical advice
  · Not tested with people".
- Charts (slide 5) state the unit (prompts passed), the denominator (n = 141, or 51 for the check-in
  slice) and the seed.
- Anything not built is labelled CONCEPT: the reinforcement-learning stage (slides 5 and 8), every
  validation step (slide 7) and every next step (slide 8).
- No library, platform or model name appears in slide text. The training stages read "Fine-tuned
  (stage 1)" and "Preference-tuned (stage 2)". The only platform name on any slide is inside the
  demo URL on slide 8.

Rebuild (from the repo root):

```sh
python docs/daypart/submission/deck/build_deck.py <capture_dir>   # needs python-pptx, Pillow; omit the dir to reuse screens/
node docs/daypart/submission/deck/deck_pdf.js docs/daypart/submission/deck   # needs playwright
```

`<capture_dir>` is the output of [`../video/capture/capture.js`](../video/capture/capture.js),
plus `s4c-pii-1280.png`, a screenshot of the personal-data refusal. It was taken on the hosted
build with the fictional text "My name is Sam Lee, email sam.lee@example.com, slept 7 hours" (422,
nothing saved).

# FHDIC demo video: shot list, narration draft and edit plan (HAC-65)

**Status: draft. The video has not been made.** Two inputs are still missing:
- the HAC-38 fix for the hosted passport. `GET /api/journals/{id}/passport` returns 500 on the
  hosted build as of 2026-11-10 01:45 UTC, so segment 3 can't be filmed yet.
- the HAC-64 claim ledger. The narration below uses only what the screen shows. Any figure stays
  out until the ledger traces it.

Target length: 2:40, within the brief's 2:30–3:00 (a proposal, not an organiser rule; HAC-63
found no published video rule).

Every UI shot is a **real recording of the hosted build**:
https://supermomo668--daypart-demo-playground.us-east.modal.run, 1280×720, made with Playwright
`recordVideo` by [`capture/capture.js`](capture/capture.js). One take records the whole journey.
`clips-1280.json` records each segment's offsets, the URL, the deployed commit and every API status.
Nothing is mocked or intercepted.

## Timeline

| # | Time | Source | Shot | On-screen caption |
|---|---|---|---|---|
| 1 | 0:00–0:20 | Title card (deck slide 1) + presenter* | Problem: goals and barriers change; generic reminders don't say what they know | "Synthetic demo · simulated results · not medical advice" |
| 2 | 0:20–0:50 | **Real footage** `s2-checkin-review` | Type "slept 6 hours and walked 8000 steps" → Check in → review rows with source snippet, date, method → Confirm → Save | "Nothing is saved until you review it" |
| 3 | 0:50–1:20 | **Real footage** `s3-passport` | Passport cards (observed/simulated, data age, source) → open **Evidence thread** | "Every value shows where it came from" |
| 4a | 1:20–1:32 | **Real footage** `s4a-next-step` | Suggested next step and its reason: Choose / Defer / Ask a professional | "The person chooses. Nothing is imposed." |
| 4b | 1:32–1:40 | **Real footage** `s4b-safety` | Check-in "Can you give me a crisis line to call?" → hand-off notice; nothing extracted or saved | "A real refusal: crisis language goes to a person" |
| 4c | 1:40–1:45 | **Real footage** `s4c-real-input` | Footer **Real input** → server refuses (HTTP 403) and lists the open gates | "Real health data is switched off" |
| 5 | 1:45–2:15 | **Real footage** `s5-lab` | Learning lab: base vs SFT vs DPO and scripted baselines, each with run ID, split, seed, failures | "Synthetic episodes · simulated results · not patient outcomes" |
| 6 | 2:15–2:40 | Deck slide 3/5 (system + validation) + presenter* | How it works; what was tested and how | footer "synthetic / simulated results" |
| 7 | 2:40–3:00 | Deck slide 6/8 (limits, access) + presenter* | Limits; demo link; not for clinical use | demo URL as text |

\* Presenter and voice: HeyGen if the existing plan covers the render. HeyGen gets only the
narration text below: no health data, no screenshots, no claims beyond the script. If a render
needs new spend or a plan upgrade, the presenter is dropped and the video ships as captions over
footage and slides.

## Narration draft (≈ 360 words, ≈ 2:40 at 135 wpm)

> Reconcile against the HAC-64 ledger before any voice render. Lines marked ⟦ledger⟧ wait for a traced figure.

1. People's goals and barriers change from week to week. Most reminders can't tell you what they
   know about you, or why they suggest what they do.
2. Clinical Human Clone is a synthetic-first prototype. Everything you'll see uses made-up input
   and simulated results. It is not medical advice.
3. A check-in starts as a plain sentence. The clone proposes what it found: each value with its
   source text, date and method. Nothing is saved until the person confirms, corrects or discards it.
4. Confirmed values become the Health Clone Passport. Each card says whether it was observed or
   simulated, how old the data is, and where it came from. Open the evidence thread to follow one
   value from the check-in to the card. Cards without enough evidence say so instead of showing a number.
5. The suggested next step comes with its reason. The person can choose it, defer it or ask a
   professional.
6. Some things it will not do. Crisis language is not processed: the person is pointed to a human,
   and nothing is saved. Real health data is switched off, and the server refuses to turn it on.
7. Separately, a learning lab compares a base model with fine-tuned candidates and scripted
   baselines on synthetic episodes. Every number links to its run, split and seed. These are
   simulated results, not patient outcomes. ⟦ledger: which figure, if any, is spoken⟧
8. ⟦ledger: system and validation sentence from the deck outline, slide 3/5⟧
9. This is a prototype. It gives no diagnosis or treatment, it has not been clinically validated,
   and real input needs consent, privacy and clinical oversight first. The demo link is in our
   submission.

## Edit plan

- Cut the single take at the `clips-1280.json` offsets. Trim dead waits and never speed up typing
  beyond 2×. A speed-up gets a "sped up" tag.
- Transitions: 0.4 s cross-fade between segments (ffmpeg `xfade`), and a cut inside a segment.
- Captions: burned-in segment labels (top band, ≥ 32 px, ink on white, contrast ≥ 7:1) plus the
  narration as `captions.srt` (side-car, ≤ 2 lines, ≤ 42 chars per line).
- Zoom: 1.25× crop on the review rows (seg 2) and the evidence thread (seg 3). Crop only, no
  re-rendered UI.
- Persistent corner tag on every frame: "Synthetic demo · simulated results".
- Export: H.264 1280×720 30 fps, AAC, target < 50 MB. The MP4 goes on HAC-65 as an attachment,
  not into git.
- Committed alongside: `captions.srt`, `transcript.md`, `clips-1280.json`, the ffmpeg edit script,
  and this file.

## Known UI issue seen in the dry run (not fixed here)

At 1280 px the learning-lab table's **Failures** and **Metric** columns wrap mid-word
("Fail/ure/s", "bou/ndar/y"), because the page is capped at a 44rem measure. That reads badly on
camera. It belongs to the HAC-38 owner. The cut will crop around it if it's not fixed first.

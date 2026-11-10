# FHDIC demo video: shot list and edit (HAC-65)

**Status: made.** `clinical-human-clone-demo.mp4` is 2:37 long, 1920×1080, 30 fps, H.264 (CRF 24)
and 9.3 MB, under the 10 MB attachment limit (md5 `d11077c899317ec37f56b108d51ab5aa`). It is
attached to HAC-65 (attachment `ff59472d-b4e1-41f9-95d1-9fdd75307bae`) and is not in git. Captions are burned in and also provided as
[`captions.srt`](captions.srt). The full text and timing are in [`transcript.md`](transcript.md).

**No presenter and no voice-over.** HeyGen was not used. A read-only check on 2026-11-10 found no
subscription: the account is a pay-as-you-go wallet with USD 0.97 left and auto-reload turned on
(it tops up USD 10 when the balance falls below USD 5). Any render would have triggered new spend,
which the brief rules out. Nothing was sent to HeyGen and nothing was rendered there. If a person
later adds a voice track, the narration is the caption text in `captions.srt`, and its timing
already fits.

**Timeline.** 9 of the 14 segments are real footage and 5 are deck slides. The footage is cut
from one real Playwright recording of the hosted build, made by
[`capture/capture.js`](capture/capture.js) at 1280×720:
https://supermomo668--daypart-demo-playground.us-east.modal.run, deployed commit
`e50ebb71aaeb7b61a42cd81c7481e1a17e49fe98`, recorded 2026-11-10 21:10 UTC.
[`capture/clips-1280.json`](capture/clips-1280.json) records each clip's offsets, URL and every
API status. Nothing is mocked, intercepted, re-staged or sped up.

| # | time | source | shot |
|---|---|---|---|
| 1 | 0:00–0:12 | slide 1 | Problem and user |
| 2 | 0:11–0:29 | **real footage** `/` → `/#review` | Type a four-part sentence → 3 proposals with their words → correct sleep to 6.5 h, confirm 2 → save |
| 3 | 0:29–0:43 | **real footage** `/#passport` | Passport cards → evidence thread opened → a withheld card |
| 4 | 0:43–0:50 | **real footage** `/#next` | Next step after a pain report routes to a person → Choose |
| 5 | 0:50–0:59 | **real footage** `/#today` | Crisis check-in → fixed hand-off, nothing saved |
| 6 | 0:59–1:08 | **real footage** `/admin#input` | Request real input → server refuses (403), 12 gates open |
| 7 | 1:08–1:14 | **real footage** `/#timeline` | What each saved check-in changed |
| 8 | 1:14–1:24 | **real footage** `/admin#lab` | Learning lab rows with run ID, split, seed and failures |
| 9 | 1:24–1:40 | slide 5 | Learning and evidence (synthetic / simulated results) |
| 10 | 1:40–1:46 | **real footage** `/admin#pipeline` | Live loop, then the offline training stages (RL stage marked "proposed, not built") |
| 11 | 1:46–2:00 | slide 3 | How it works |
| 12 | 1:59–2:13 | slide 6 | Responsible AI and limits |
| 13 | 2:13–2:25 | slide 7 | Feasibility and path to deployment |
| 14 | 2:25–2:37 | slide 8 | Impact and next steps, with the prototype and source links |

The order follows the brief: problem → check-in and correction → passport provenance → bounded
step and real refusals → learning lab → system and validation → limits.

## Edit

[`make_video.py`](make_video.py) holds the whole edit as one segment plan, which writes the MP4,
`captions.srt`, `transcript.md` and `edit-plan.json` together.

- Footage and slides are each scaled to 1600×900 on a dark 1920×1080 frame.
- A top band labels every segment ("Real recording · hosted build · …" or "Slide N · …").
- Every frame carries the tag "Synthetic demo · simulated results · not medical advice".
- Segments join with a 0.4 s cross-fade.
- A footage segment may end on a 1–3 s hold of its own last frame, so the captions can be read.
- Captions are single lines, white on near-black, burned in at the bottom.
- The audio track is silent (AAC), for player compatibility.

Rebuild:

```sh
BUILD_SHA=<deployed sha> node capture/capture.js <cap_dir> 1280
DSF=1.25 node ../deck/deck_pdf.js ../deck <slides_dir>
python make_video.py --footage <cap_dir> --slides <slides_dir> --out clinical-human-clone-demo.mp4 \
  --ffmpeg <full ffmpeg> --font LiberationSans-Regular.ttf --bold LiberationSans-Bold.ttf
```

A new capture is a new take, so its offsets differ, and the plan's captions were timed to this
take. Re-check `clips-1280.json` before re-cutting.

The judge-path check is in [judge-path.md](judge-path.md).

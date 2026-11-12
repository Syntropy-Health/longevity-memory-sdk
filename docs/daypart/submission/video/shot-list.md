# FHDIC demo video: shot list and edit (HAC-65, re-filmed for HAC-77)

**Status: made.** `clinical-human-clone-demo.mp4` is 3:00 long, 1920×1080, 30 fps, H.264 (CRF 27)
and 9.9 MB, under the 10 MB attachment limit (md5 `d4d2fb13c4402dbe3fbd6231ceec6ba4`). It is attached to HAC-77 and is not in
git. The HAC-65 cut (2:37, build e50ebb7) is superseded. Captions are burned in and are also in
[`captions.srt`](captions.srt). The full text and timing are in [`transcript.md`](transcript.md).

**No presenter and no voice-over.** HeyGen was not used, and nothing new was spent. A read-only
check on 2026-11-10 found no subscription: the account is a pay-as-you-go wallet with USD 0.97 left,
and auto-reload is on (it tops up USD 10 when the balance falls below USD 5). Any render would
have triggered new spend. If a person later adds a voice track, the narration is the caption text,
and its timing already fits.

**Timeline.** 8 of the 15 segments are real footage (about 90 s with holds) and 7 are deck slides.
The footage is cut from one real Playwright recording of the hosted build, made by
[`capture/capture.js`](capture/capture.js) at 1280×720:
https://supermomo668--daypart-demo-playground.us-east.modal.run, deployed commit
`4ba3adb28a44940b66cb6e3c9d62e7fa76e1df2f` (HAC-75 and HAC-76), recorded 2026-11-11 02:37 UTC.
[`capture/clips-1280.json`](capture/clips-1280.json) records each clip's offsets and URL, and the
status of every API call. Nothing is mocked, intercepted, re-staged or sped up. Following HAC-76,
the video shows the production flow and has no "Real input" screen.

| # | time | source | shot |
|---|---|---|---|
| 1 | 0:00–0:12 | slide 1 | Problem and user |
| 2 | 0:12–0:29 | **real footage** `/` → `/#review` | Type a four-part sentence → 3 proposals with their words → correct sleep to 6.5 h, confirm 2 → save |
| 3 | 0:28–0:43 | **real footage** `/#passport` | Passport cards → evidence thread opened → a withheld card |
| 4 | 0:42–0:55 | **real footage** `/#passport` | **Inclinations:** what weighs most → next steps, each linked to a driver with "Why:" |
| 5 | 0:54–1:02 | **real footage** `/#next` | Next step after a pain report routes to a person → Choose |
| 6 | 1:02–1:11 | **real footage** `/#today` | Crisis check-in → fixed hand-off, nothing saved |
| 7 | 1:10–1:17 | **real footage** `/#timeline` | What each saved check-in changed |
| 8 | 1:16–1:27 | **real footage** `/admin#pipeline` | Research console Overview: headline results, check-in loop, offline training steps |
| 9 | 1:26–1:39 | **real footage** `/admin#lab` | Results: training steps on 141 prompts; coaching approaches incl. the learned policy (84.0%) |
| 10 | 1:38–1:54 | slide 5 | Learning and evidence (synthetic / simulated results) |
| 11 | 1:54–2:11 | slide 6 | What helps this member: question library, reward model, learned policy (GRPO) |
| 12 | 2:10–2:23 | slide 3 | How it works |
| 13 | 2:23–2:37 | slide 7 | Responsible AI and limits |
| 14 | 2:37–2:49 | slide 8 | Feasibility and path to deployment |
| 15 | 2:48–3:00 | slide 9 | Impact and next steps, with the prototype and source links |

Exact segment times are in [`edit-plan.json`](edit-plan.json). The order follows the brief:
problem → check-in and correction → passport provenance and inclinations → bounded step and a real
refusal → results → system and validation → limits.

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
python ../deck/export_deck.py <demo base url> --png <slides_dir>   # 1600x900 slide frames from /deck
python make_video.py --footage <cap_dir> --slides <slides_dir> --out clinical-human-clone-demo.mp4 \
  --ffmpeg <full ffmpeg> --font LiberationSans-Regular.ttf --bold LiberationSans-Bold.ttf --crf 27
```

A new capture is a new take, so its offsets differ, and the plan's captions were timed to this
take (each caption must end before its clip plus hold). Re-check `clips-1280.json` before re-cutting.

HAC-86 re-cut (slides only). The raw take is not kept, so `recut_slides.py` keeps the footage block of
the last cut frame for frame and re-renders only the slide segments from the web deck:

```sh
python ../deck/export_deck.py <demo base url> --png <slides_dir>
python recut_slides.py --old <HAC-77 mp4> --old-plan <its edit-plan.json> --old-srt <its captions.srt> \
  --slides <slides_dir> --out clinical-human-clone-demo.mp4 --ffmpeg <full ffmpeg> --fonts <Liberation Sans dir>
```

The judge-path check is in [judge-path.md](judge-path.md).

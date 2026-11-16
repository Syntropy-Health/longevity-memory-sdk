# FHDIC demo video v2 (HAC-92): HeyGen-styled, scientific structure

This replaces the HAC-65/HAC-77/HAC-86 slide-and-footage cut (`../shot-list.md`) to meet the board's
2026-11-15 requirement (HAC-90). It is styled on the HeyGen video made for the Meta submission
(`28e555de…`, HAC-24/HAC-25), with the same presenter (*Sable*, digital twin, `avatar_v`), the same voice
(*Clinical Warmth*) and the same layout: a cream card panel with the presenter on the right, and
full-frame graphics as B-roll. It reuses none of that video's content. The register is
**hypothesis → method → evidence → limit**. Every spoken number comes from the
[evidence ledger](../../evidence-ledger.md), and anything not built is labelled *concept*.

**Not in git:** the MP4. It is attached to HAC-92 and is private: no share link, not uploaded,
not submitted.

| file | what |
|---|---|
| [`script.json`](script.json) | **the editable script**: 15 segments, each with section, source, narration (`text`), spoken form (`say`, where numbers are spelled out for the voice) and ledger rows |
| [`captions.srt`](captions.srt) | captions (also burned in) |
| [`transcript.md`](transcript.md) | full narration with times, sources and ledger rows |
| [`segments.md`](segments.md) | **segment table**: real footage vs HeyGen vs local render, with time ranges |
| [`coverage.md`](coverage.md) | **rubric coverage**, mapped to HAC-91 `video-rubric` (landed 2026-11-16): its 8 inferred criteria with weights and published/inferred tag → time range → evidence rows; the §3e beat budget against the cut's seconds; and where the cut covers lapse → recovery and sustained change, with the gaps |
| [`clips-1280.json`](clips-1280.json) | the footage take: URL, deployed commit, clip offsets, every API status |
| [`cards.html`](cards.html) | the cards. Each number names its ledger row in `data-ledger` |
| `tts.py`, `render_cards.js`, `make_video_v2.py` | the build |

## What HeyGen made, and what it did not

- **Voice:** HeyGen TTS `heygen-voice-1-turbo-free` (no charge), one call per segment, with only the
  script text sent. It is played at ×1.06 tempo, with pitch kept.
- **Presenter:** a single HeyGen `avatar_v` render of *Sable*, lip-synced to the presenter
  segments' narration audio. Only that audio was sent: no footage, no slides, no health data. The
  presenter fills the right-hand column on the 5 presenter segments.
- **Everything else is local:** the real footage, every card and chart, and the captions. HeyGen
  drew no product screen, feature or result, so it cannot have invented one.

## Footage

One real Playwright take of the hosted build, made by [`../capture/capture.js`](../capture/capture.js)
unchanged at 1280×720 (see `clips-1280.json` for the URL, the commit and the recording time).
Nothing is mocked, intercepted, re-staged or sped up. The only status of 400 or above is the
expected 422 personal-data refusal, which the cut does not show. `capture.js` stamps offsets from its own clock,
and the webm starts 1.15 s later, so the edit subtracts `TAKE_LAG` (measured from six page changes).

## Rebuild

```sh
HEYGEN_API_KEY=… python tts.py --out <tts>                                  # free
BUILD_SHA=<deployed sha> node ../capture/capture.js <cap> 1280
python make_video_v2.py plan --tts <tts> --clips <cap>/clips-1280.json --work <w> --ffmpeg <ffmpeg>
NODE_PATH=<playwright> node render_cards.js <w>/cards-jobs.json <cards> <fonts>   # Space Grotesk, JetBrains Mono (OFL)
HEYGEN_API_KEY=… python make_video_v2.py presenter --work <w> --cap-usd <cap>   # paid: refuses if the worst-case quote passes the cap
python make_video_v2.py compose --work <w> --footage <cap>/<take>.webm --cards <cards> --fonts <fonts> --ffmpeg <ffmpeg> --out <mp4>
python make_video_v2.py docs --work <w>                                      # transcript.md, segments.md, coverage.md
cp <w>/captions.srt .
```

A new capture is a new take. Re-check the `FOOTAGE` windows and `TAKE_LAG` in `make_video_v2.py`
against its `clips-1280.json`. A changed presenter line means a new presenter render, and a new spend.

`presenter` polls for at most `--poll-timeout` seconds (default 3600); re-running it keeps polling the
same video, with no new spend. If `<w>/presenter.json` records a failed render, `presenter` stops: read
the failure, then delete that file to submit a new, paid render.

## HeyGen spend (HAC-92, cap USD 30)

| step | video id | result | wallet |
|---|---|---|---|
| presenter render, attempt 1 | `0cb03c2a…` | failed, insufficient credit (no charge); this triggered the USD 10 auto-reload | 0.97 → 10.97 |
| presenter render, attempt 2 | `76759669…` | completed, 59.2 s, avatar_v 1080p, private | 10.97 → 3.88 |
| narration TTS | n/a | `heygen-voice-1-turbo-free` | no charge |

Render cost **USD 7.09**. Card charged: **USD 10.00** (one auto-reload). Total is within the USD 30 cap. Nothing was shared publicly.

**Round 2 (CTO change request, 2026-11-16):** s12 now states the lapse-recovery result (L62) in place of the
trait-recovery line (L75). Its narration was re-voiced with the free TTS and its card re-rendered locally. No
presenter line changed: `presenter.wav` is byte-identical, so the same render is reused. **No new HeyGen spend.**
The cut is 2:56.1. The issue attachment is encoded at CRF 31, to fit the 10 MB limit.

"""Edit the FHDIC demo video (HAC-65) from real hosted footage and deck slides.

    python make_video.py --footage <capture_dir> --slides <slide_png_dir> --out <mp4> [--ffmpeg BIN] [--font TTF]

<capture_dir> holds the Playwright take and clips-1280.json written by capture/capture.js.
<slide_png_dir> holds slide-N.png rendered by ../deck/deck_pdf.js with DSF=1.25 (1600x900).

One plan (SEGMENTS below) drives three outputs, so they cannot disagree:
  the MP4 (1920x1080, 30 fps, H.264, silent AAC track; captions burned in),
  captions.srt (side-car, same text and timing) and transcript.md (next to this file).

No voice-over and no presenter: HeyGen was not used (rendering would have needed new spend; see
shot-list.md). Every UI shot is a cut of the single real recording; nothing is re-staged, mocked or
sped up. A held last frame ("hold") is a still of the same recording, used so captions can be read.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FPS, XF = 30, 0.4
BG = "0x0B0D12"

# kind, source (clip id or slide number), hold seconds (footage) or duration (slide), label, captions
# captions: (start, end, text) relative to the segment start. Every figure traces to a ledger row.
SEGMENTS = [
    ("slide", 1, 12, "Slide 1 · Problem and user", [
        (0.3, 6, "People's goals and barriers change week to week."),
        (6, 11.8, "Generic reminders don't show what they know about you, or why they suggest something.")]),
    ("clip", "s2-checkin-review", 2.0, "Real recording · hosted build · check-in and review", [
        (0.3, 5, "A synthetic check-in starts as one plain sentence."),
        (5, 10, "It proposes 3 values, each with the words it came from. Mood gave none."),
        (10, 14.5, "Sleep is corrected to 6.5 hours; the other two are confirmed."),
        (14.5, 17.6, "Nothing is saved until the review is submitted.")]),
    ("clip", "s3-passport", 2.0, "Real recording · hosted build · Health Clone Passport", [
        (0.3, 5, "Saved values update the Health Clone Passport."),
        (5, 10, "The evidence thread traces one value from the check-in to the card."),
        (10, 14.2, "A card with no value in 14 days is withheld, not guessed.")]),
    ("clip", "s4a-next-step", 2.0, "Real recording · hosted build · suggested next step", [
        (0.3, 4, "After a pain report, the next step routes to a person."),
        (4, 7.4, "The person can choose, defer or ask a professional.")]),
    ("clip", "s4b-safety", 2.0, "Real recording · hosted build · crisis hand-off", [
        (0.3, 4.5, "Crisis language is not processed."),
        (4.5, 8.7, "A fixed hand-off points to a person. Nothing is saved.")]),
    ("clip", "s5c-real-input", 2.0, "Real recording · hosted build · research console, real input", [
        (0.3, 5, "Real health data is switched off in this build."),
        (5, 9.5, "The server refuses the request: 12 of 12 governance gates are open.")]),
    ("clip", "s4d-timeline", 1.0, "Real recording · hosted build · timeline", [
        (0.3, 6.1, "The timeline shows what each saved check-in changed.")]),
    ("clip", "s5b-lab", 3.0, "Real recording · hosted build · learning lab", [
        (0.3, 5, "The learning lab reads committed training and evaluation runs."),
        (5, 10, "Each number carries its run ID, split, seed and failure count.")]),
    ("slide", 5, 16, "Slide 5 · Learning and evidence (synthetic / simulated results)", [
        (0.3, 6, "On 141 held-out synthetic prompts, the base model passed 45."),
        (6, 11, "Both fine-tuned stages passed all 141. 90 base replies were empty."),
        (11, 15.8, "These are simulated results, not patient outcomes.")]),
    ("clip", "s5a-pipeline", 1.0, "Real recording · hosted build · research console, pipeline", [
        (0.3, 6.3, "The research console shows the live loop, then the offline training stages.")]),
    ("slide", 3, 14, "Slide 3 · How it works", [
        (0.3, 7, "Live: check-in, safety checks, proposals, review, memory, passport."),
        (7, 13.8, "Offline: synthetic members, evaluation, fine-tuning, frozen comparison.")]),
    ("slide", 6, 14, "Slide 6 · Responsible AI and limits", [
        (0.3, 7, "Synthetic data only. No diagnosis, treatment or dosing. No clinical review."),
        (7, 13.8, "The rules caught 74 of 74 test violations: a measurement, not a proof.")]),
    ("slide", 7, 12, "Slide 7 · Feasibility and path to deployment", [
        (0.3, 6, "It runs today as a hosted prototype."),
        (6, 11.8, "Reaching people needs consent, privacy, clinical oversight and a study first.")]),
    ("slide", 8, 12, "Slide 8 · Impact and next steps", [
        (0.3, 6, "Next: a clinical reviewer, a consented pilot and a pre-registered measure."),
        (6, 12, "The prototype link is in the submission.")]),
]
TAG = "Synthetic demo · simulated results · not medical advice"


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def ts(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def build(footage: Path, slides: Path, out: Path, ffmpeg: str, font: str, bold: str, crf: int = 24):
    meta = json.loads((footage / "clips-1280.json").read_text())
    webm = footage / meta["video"]
    clips = {c["id"]: c for c in meta["clips"]}
    tmp = Path(tempfile.mkdtemp(prefix="hac65-edit-"))
    parts, durs, plan = [], [], []
    for i, (kind, src, hold, label, caps) in enumerate(SEGMENTS):
        lf = tmp / f"label{i}.txt"; lf.write_text(label)
        tf = tmp / "tag.txt"; tf.write_text(TAG)
        draw = (f"drawtext=fontfile={bold}:textfile={lf}:fontsize=30:fontcolor=white:x=160:y=26,"
                f"drawtext=fontfile={font}:textfile={tf}:fontsize=24:fontcolor=0xC9CDD6:x=w-160-tw:y=30")
        place = f"scale=1600:900:flags=lanczos,pad=1920:1080:160:80:color={BG},setsar=1,fps={FPS},format=yuv420p"
        seg = tmp / f"seg{i:02}.mp4"
        if kind == "clip":
            c = clips[src]
            dur = (c["end"] - c["start"]) + hold
            vf = f"{place},tpad=stop_mode=clone:stop_duration={hold},{draw}"
            run([ffmpeg, "-y", "-ss", f"{c['start']}", "-to", f"{c['end']}", "-i", str(webm), "-vf", vf,
                 "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-t", f"{dur}", str(seg)])
            plan.append(dict(kind="real footage", source=f"{meta['video']} {c['start']}–{c['end']} s", url=c["url"],
                             build_sha=meta["build_sha"], recorded_at=meta["recorded_at"], label=label))
        else:
            dur = hold
            vf = f"{place},{draw}"
            run([ffmpeg, "-y", "-loop", "1", "-framerate", f"{FPS}", "-t", f"{dur}", "-i", str(slides / f"slide-{src}.png"),
                 "-vf", vf, "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", str(seg)])
            plan.append(dict(kind="deck slide", source=f"deck slide {src}", url=None, label=label))
        parts.append(seg); durs.append(dur)
    # Segment start times on the final timeline (each cross-fade overlaps XF seconds).
    starts, t = [], 0.0
    for d in durs:
        starts.append(t); t += d - XF
    total = t + XF
    # SRT
    srt, n = [], 1
    for (kind, src, hold, label, caps), st in zip(SEGMENTS, starts):
        for a, b_, text in caps:
            srt.append(f"{n}\n{ts(st + a)} --> {ts(st + b_)}\n{text}\n"); n += 1
    srt_path = HERE / "captions.srt"
    srt_path.write_text("\n".join(srt), encoding="utf-8")
    # xfade chain
    inputs, fc, prev = [], [], "0:v"
    for p in parts:
        inputs += ["-i", str(p)]
    acc = durs[0]
    for k in range(1, len(parts)):
        off = acc - XF
        outl = f"x{k}"
        fc.append(f"[{prev}][{k}:v]xfade=transition=fade:duration={XF}:offset={off:.3f}[{outl}]")
        prev, acc = outl, off + durs[k]
    style = ("FontName=Liberation Sans,FontSize=11,PrimaryColour=&H00FFFFFF,BackColour=&H00120D0B,"
             "BorderStyle=4,Outline=0,Shadow=0,MarginV=10,Alignment=2")
    fontsdir = str(Path(font).parent)
    fc.append(f"[{prev}]subtitles={srt_path}:fontsdir={fontsdir}:force_style='{style}'[v]")
    cmd = [ffmpeg, "-y", *inputs, "-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
           "-filter_complex", ";".join(fc), "-map", "[v]", "-map", f"{len(parts)}:a",
           "-c:v", "libx264", "-preset", "slow", "-crf", f"{crf}", "-pix_fmt", "yuv420p", "-r", f"{FPS}",
           "-c:a", "aac", "-b:a", "64k", "-shortest", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    # transcript
    lines = ["# FHDIC demo video: transcript (HAC-65)", "",
             f"Length {int(total // 60)}:{int(total % 60):02} · 1920×1080 · 30 fps · captions burned in and in "
             "[`captions.srt`](captions.srt) · **no voice-over and no presenter** (HeyGen not used; see "
             "[shot-list.md](shot-list.md)).", "",
             f"Footage: one real Playwright recording of the hosted build, {meta['url']}, deployed commit "
             f"`{meta['build_sha']}`, recorded {meta['recorded_at']}. Slides: "
             "[`../deck/clinical-human-clone-deck.pdf`](../deck/clinical-human-clone-deck.pdf).", "",
             "| # | time | source | on screen | captions |", "|---|---|---|---|---|"]
    for i, ((kind, src, hold, label, caps), st, d, pl) in enumerate(zip(SEGMENTS, starts, durs, plan), 1):
        where = f"{pl['kind']}: `{pl['url'].replace(meta['url'], '') or '/'}` ({pl['source']})" if pl["url"] else pl["kind"]
        lines.append(f"| {i} | {ts(st)[3:8]}–{ts(st + d)[3:8]} | {where} | {label} | " + " ".join(c[2] for c in caps) + " |")
    (HERE / "transcript.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (HERE / "edit-plan.json").write_text(json.dumps(dict(total_seconds=round(total, 2), crossfade=XF, segments=[
        dict(n=i, start=round(st, 2), duration=round(d, 2), **pl) for i, (st, d, pl) in enumerate(zip(starts, durs, plan), 1)]), indent=2) + "\n")
    print(f"{out}  {total:.1f} s  {len(SEGMENTS)} segments")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--footage", required=True, type=Path)
    ap.add_argument("--slides", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--ffmpeg", default="ffmpeg")
    ap.add_argument("--font", required=True, help="regular sans TTF (Liberation Sans)")
    ap.add_argument("--bold", required=True, help="bold sans TTF")
    ap.add_argument("--crf", type=int, default=24, help="x264 quality; 24 keeps the MP4 under the 10 MB attachment limit")
    a = ap.parse_args()
    build(a.footage, a.slides, a.out, a.ffmpeg, a.font, a.bold, a.crf)

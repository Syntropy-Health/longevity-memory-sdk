"""Edit the FHDIC demo video (HAC-65; re-cut for HAC-77) from real hosted footage and deck slides.

    python make_video.py --footage <capture_dir> --slides <slide_png_dir> --out <mp4> [--ffmpeg BIN] [--font TTF]

<capture_dir> holds the Playwright take and clips-1280.json written by capture/capture.js.
<slide_png_dir> holds slide-N.png (1600x900) from ../deck/export_deck.py --png.
Without the raw footage, recut_slides.py re-renders only the slide segments over the last MP4 (HAC-86).

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
    # HAC-86: slide numbers are the web deck's (/deck); the order is top-down: problem, design, the real
    # footage, technical solution, next steps.
    ("slide", 1, 12, "Problem", [
        (0.3, 6, "Healthy routines break when the week changes."),
        (6, 11.8, "Generic reminders neither know you nor explain why.")]),
    ("slide", 3, 12, "Design · the member flow", [
        (0.3, 6, "One sentence in, a reviewed record out."),
        (6, 11.8, "Check in, review, passport, Inclinations, next step. Pain or crisis goes to a person.")]),
    ("clip", "s2-checkin-review", 2.0, "Real recording · hosted build · check-in and review", [
        (0.3, 5, "A synthetic check-in starts as one plain sentence."),
        (5, 10, "It proposes 3 values, each with the words it came from. Mood gave none."),
        (10, 14, "Sleep is corrected to 6.5 hours; the other two are confirmed."),
        (14, 16.8, "Nothing is saved until the review is submitted.")]),
    ("clip", "s3-passport", 2.0, "Real recording · hosted build · Health Clone Passport", [
        (0.3, 5, "Saved values update the Health Clone Passport."),
        (5, 10, "The evidence thread traces one value from the check-in to the card."),
        (10, 14.2, "A card with no value in 14 days is withheld, not guessed.")]),
    ("clip", "s3b-inclinations", 2.5, "Real recording · hosted build · passport, Inclinations", [
        (0.3, 6, "Inclinations: what weighs most for this member, from 7 short questions (simulated answers)."),
        (6, 12.4, "Each next step is linked to one of them, with its reason. A prompt for the care team, not a care plan.")]),
    ("clip", "s4a-next-step", 2.0, "Real recording · hosted build · suggested next step", [
        (0.3, 4, "After a pain report, the next step routes to a person."),
        (4, 7.4, "The person can choose, defer or ask a professional.")]),
    ("clip", "s4b-safety", 2.0, "Real recording · hosted build · crisis hand-off", [
        (0.3, 4.5, "Crisis language is not processed."),
        (4.5, 8.8, "A fixed hand-off points to a person. Nothing is saved.")]),
    ("clip", "s4d-timeline", 1.0, "Real recording · hosted build · timeline", [
        (0.3, 6.1, "The timeline shows what each saved check-in changed.")]),
    ("clip", "s5a-overview", 2.0, "Real recording · hosted build · research console, overview", [
        (0.3, 5.5, "The research console leads with its results, in plain language."),
        (5.5, 10.4, "Training runs offline. No AI model is used in the check-in loop.")]),
    ("clip", "s5b-results", 3.0, "Real recording · hosted build · research console, results", [
        (0.3, 5.5, "Each training step was tested on the same 141 held-out practice prompts."),
        (5.5, 11.9, "With simulated members, the learned approach logged 84.0% of days, against 83.3% for the best fixed one.")]),
    ("slide", 6, 13, "Technical · architecture", [
        (0.3, 6.5, "Rules run live, with no model call in the check-in loop."),
        (6.5, 12.8, "Training and evaluation run offline and publish versioned results.")]),
    ("slide", 7, 14, "Technical · memory and the honesty layer", [
        (0.3, 7, "Memory keeps only what the person confirmed."),
        (7, 13.8, "The boundary rules caught 74 of 74 labelled violations, with 0 false alarms on 128 rows.")]),
    ("slide", 8, 17, "Technical · question library, reward model, GRPO", [
        (0.3, 6, "7 answers recover each hidden trait 76–91% of the time."),
        (6, 11.5, "The reward model reads term by term; its top message type matches for 83%."),
        (11.5, 16.8, "GRPO learns which message type to send.")]),
    ("slide", 9, 16, "Technical · results", [
        (0.3, 6, "On 141 held-out prompts, the base model passed 45."),
        (6, 11, "Both trained stages passed all 141."),
        (11, 15.8, "The learned policy reached 0.840 mean simulated adherence, against 0.833 for the best script.")]),
    ("slide", 10, 12.8, "Next steps", [
        (0.3, 6.5, "Next: a clinical reviewer, a consented pilot, a measured result."),
        (6.5, 12.6, "The prototype and this deck are live at the demo link.")]),
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
    tmp = Path(tempfile.mkdtemp(prefix="hac77-edit-"))
    parts, durs, plan = [], [], []
    for i, (kind, src, hold, label, caps) in enumerate(SEGMENTS):
        lf = tmp / f"label{i}.txt"; lf.write_text(label)
        tf = tmp / "tag.txt"; tf.write_text(TAG)
        draw = f"drawtext=fontfile={bold}:textfile={lf}:fontsize=30:fontcolor=white:x=160:y=26"
        if kind == "clip":  # HAC-86: the tag rides on the footage only; the slides carry no caveat labels
            draw += f",drawtext=fontfile={font}:textfile={tf}:fontsize=24:fontcolor=0xC9CDD6:x=w-160-tw:y=30"
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
    lines = ["# FHDIC demo video: transcript (HAC-77)", "",
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

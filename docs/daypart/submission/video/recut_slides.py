"""Re-cut the demo video's slide segments from the web deck (HAC-86), keeping the real footage as it is.

    python recut_slides.py --old <hac77.mp4> --old-plan <edit-plan.json> --old-srt <captions.srt> \
        --slides <slide_png_dir> --out <mp4> --ffmpeg BIN --fonts <dir with LiberationSans-*.ttf>

The raw Playwright take behind make_video.py is not kept in the repo, so this script takes the footage
from the last cut (HAC-77, 180.23 s): the run of real-footage segments is copied frame for frame, with
its burned-in labels and captions, from the end of its first cross-fade to the start of its last. Every
slide segment in make_video.SEGMENTS is rendered fresh from <slide_png_dir>/slide-N.png (1600x900, from
../deck/export_deck.py --png), framed like the footage (1600x900 at 160,80 on 1920x1080) with its label
and burned captions. The cut is then joined with the same 0.4 s cross-fades. It rewrites captions.srt,
transcript.md and edit-plan.json next to this file, so the three still agree with the MP4.
Needs ffmpeg with libx264, libass and xfade, and Python Playwright to draw the slide frames.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from make_video import BG, FPS, SEGMENTS, XF, ts

HERE = Path(__file__).resolve().parent
STYLE = ("FontName=Liberation Sans,FontSize=11,PrimaryColour=&H00FFFFFF,BackColour=&H00120D0B,"
         "BorderStyle=4,Outline=0,Shadow=0,MarginV=10,Alignment=2")
FRAME = """<!doctype html><html><head><meta charset=utf-8><style>
html,body{{margin:0;width:1920px;height:1080px;background:#{bg};overflow:hidden}}
b{{position:absolute;left:160px;top:22px;font:700 30px 'Liberation Sans',Arial,sans-serif;color:#fff}}
img{{position:absolute;left:160px;top:80px;width:1600px;height:900px}}
</style></head><body><b>{label}</b><img src="{src}"></body></html>"""


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def parse_srt(path: Path):
    out = []
    for block in path.read_text(encoding="utf-8").strip().split("\n\n"):
        lines = block.strip().split("\n")
        a, b = lines[1].split(" --> ")
        out.append((secs(a), secs(b), " ".join(lines[2:])))
    return out


def secs(s: str) -> float:
    h, m, rest = s.split(":")
    sec, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000


def slide_frames(slides: Path, tmp: Path):
    """One 1920x1080 PNG per slide segment: the footage's frame, with the segment label above the slide."""
    from playwright.sync_api import sync_playwright

    paths = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1920, "height": 1080})
        for i, (kind, src, _d, label, _c) in enumerate(SEGMENTS):
            if kind != "slide":
                continue
            html = tmp / f"frame{i}.html"
            html.write_text(FRAME.format(bg=BG[2:], label=label, src=(slides / f"slide-{src}.png").as_uri()), encoding="utf-8")
            page.goto(html.as_uri(), wait_until="load")
            paths[i] = tmp / f"frame{i}.png"
            page.screenshot(path=str(paths[i]))
        b.close()
    return paths


def build(a):
    old_plan = json.loads(a.old_plan.read_text())
    old_caps = parse_srt(a.old_srt)
    clip_idx = [i for i, s in enumerate(SEGMENTS) if s[0] == "clip"]
    assert clip_idx == list(range(clip_idx[0], clip_idx[-1] + 1)), "the footage segments must be one run"
    old_clips = [s for s in old_plan["segments"] if s["kind"] == "real footage"]
    assert len(old_clips) == len(clip_idx), "the plan's footage segments must match the last cut's"
    # Pure footage in the old cut: after its first cross-fade in, before its last cross-fade out.
    t0 = old_clips[0]["start"] + XF
    t1 = old_clips[-1]["start"] + old_clips[-1]["duration"] - XF
    tmp = Path(tempfile.mkdtemp(prefix="hac86-recut-"))
    frames = slide_frames(a.slides, tmp)
    env = dict(os.environ)
    parts, durs, kinds = [], [], []
    i = 0
    while i < len(SEGMENTS):
        kind, src, dur, label, caps = SEGMENTS[i]
        seg = tmp / f"seg{i:02}.mp4"
        if kind == "clip":
            run([a.ffmpeg, "-y", "-i", str(a.old), "-ss", f"{t0:.3f}", "-to", f"{t1:.3f}", "-an",
                 "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "18", str(seg)])
            parts.append(seg); durs.append(t1 - t0); kinds.append(("footage", None))
            i = clip_idx[-1] + 1
            continue
        srt = tmp / f"cap{i}.srt"
        srt.write_text("\n".join(f"{k}\n{ts(s)} --> {ts(e)}\n{tx}\n" for k, (s, e, tx) in enumerate(caps, 1)), encoding="utf-8")
        vf = f"fps={FPS},format=yuv420p,subtitles={srt}:fontsdir={a.fonts}:force_style='{STYLE}'"
        subprocess.run([a.ffmpeg, "-y", "-loop", "1", "-framerate", f"{FPS}", "-t", f"{dur}", "-i", str(frames[i]),
                        "-vf", vf, "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", str(seg)],
                       check=True, capture_output=True, env=env)
        parts.append(seg); durs.append(dur); kinds.append(("slide", i))
        i += 1
    starts, t = [], 0.0
    for d in durs:
        starts.append(t); t += d - XF
    total = t + XF
    inputs, fc, prev, acc = [], [], "0:v", durs[0]
    for p in parts:
        inputs += ["-i", str(p)]
    for k in range(1, len(parts)):
        off = acc - XF
        fc.append(f"[{prev}][{k}:v]xfade=transition=fade:duration={XF}:offset={off:.3f}[x{k}]")
        prev, acc = f"x{k}", off + durs[k]
    run([a.ffmpeg, "-y", *inputs, "-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
         "-filter_complex", ";".join(fc), "-map", f"[{prev}]", "-map", f"{len(parts)}:a",
         "-c:v", "libx264", "-preset", "slow", "-crf", f"{a.crf}", "-pix_fmt", "yuv420p", "-r", f"{FPS}",
         "-c:a", "aac", "-b:a", "64k", "-shortest", "-movflags", "+faststart", str(a.out)])
    # Side-cars: slide captions at their new times; footage captions moved with the footage block (clamped to it).
    srt, plan, rows, n = [], [], [], 1
    for (kind, ref), st, d in zip(kinds, starts, durs):
        if kind == "slide":
            _k, src, _d, label, caps = SEGMENTS[ref]
            for s, e, tx in caps:
                srt.append(f"{n}\n{ts(st + s)} --> {ts(st + e)}\n{tx}\n"); n += 1
            plan.append(dict(start=round(st, 2), duration=round(d, 2), kind="deck slide",
                             source=f"web deck slide {src} (/deck#/{src})", url=None, label=label))
            rows.append((st, d, "deck slide", label, " ".join(c[2] for c in caps)))
            continue
        shift = st - t0
        for s, e, tx in old_caps:
            if e > t0 and s < t1:
                srt.append(f"{n}\n{ts(max(s, t0) + shift)} --> {ts(min(e, t1) + shift)}\n{tx}\n"); n += 1
        for c in old_clips:
            s0 = max(c["start"], t0); e0 = min(c["start"] + c["duration"], t1)
            seg = {k: v for k, v in c.items() if k not in ("n", "start", "duration")}
            plan.append(dict(start=round(s0 + shift, 2), duration=round(e0 - s0, 2), **seg))
            # a caption belongs to the segment it starts in (cross-fades overlap neighbours by XF)
            caps = [tx for s, e, tx in old_caps if c["start"] <= s < c["start"] + c["duration"] - XF]
            where = f"real footage: `{re.sub(r'^https://[^/]+', '', c['url']) or '/'}` ({c['source']})"
            rows.append((s0 + shift, e0 - s0, where, c["label"], " ".join(caps)))
    (HERE / "captions.srt").write_text("\n".join(srt), encoding="utf-8")
    (HERE / "edit-plan.json").write_text(json.dumps(dict(total_seconds=round(total, 2), crossfade=XF, segments=[
        dict(n=k, **p) for k, p in enumerate(plan, 1)]), indent=2) + "\n")
    url = old_clips[0]["url"].rstrip("/").split("/#")[0]
    lines = ["# FHDIC demo video: transcript (HAC-86 re-cut)", "",
             f"Length {int(total // 60)}:{int(total % 60):02} · 1920×1080 · 30 fps · captions burned in and in "
             "[`captions.srt`](captions.srt) · **no voice-over and no presenter** (HeyGen not used; see "
             "[shot-list.md](shot-list.md)).", "",
             f"Footage: unchanged from the HAC-77 cut: one real Playwright recording of the hosted build, {url}, "
             f"deployed commit `{old_clips[0]['build_sha']}`, recorded {old_clips[0]['recorded_at']}. Slides: the web deck "
             f"({url}/deck), as printed in [`../deck/clinical-human-clone-deck.pdf`](../deck/clinical-human-clone-deck.pdf). "
             "Re-cut by [`recut_slides.py`](recut_slides.py).", "",
             "| # | time | source | on screen | captions |", "|---|---|---|---|---|"]
    for k, (st, d, where, label, caps) in enumerate(rows, 1):
        lines.append(f"| {k} | {ts(st)[3:8]}–{ts(st + d)[3:8]} | {where} | {label} | {caps} |")
    (HERE / "transcript.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{a.out}  {total:.2f} s  {len(parts)} parts  footage {t0:.2f}–{t1:.2f} s of the last cut")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True, type=Path, help="the last cut (HAC-77 MP4)")
    ap.add_argument("--old-plan", required=True, type=Path, help="its edit-plan.json")
    ap.add_argument("--old-srt", required=True, type=Path, help="its captions.srt")
    ap.add_argument("--slides", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--ffmpeg", default="ffmpeg")
    ap.add_argument("--fonts", required=True, help="directory holding Liberation Sans")
    ap.add_argument("--crf", type=int, default=26, help="x264 quality; 26 keeps the MP4 under the 10 MB attachment limit")
    build(ap.parse_args())

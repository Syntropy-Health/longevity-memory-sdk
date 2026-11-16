"""FHDIC demo video v2 (HAC-92): plan, presenter render and composition, in three steps.

    python make_video_v2.py plan      --tts <tts_dir> --clips <capture/clips-1280.json> --work <dir> --ffmpeg <ffmpeg>
    python make_video_v2.py presenter --work <dir> --cap-usd 30            # the only paid step (HeyGen)
    python make_video_v2.py compose   --work <dir> --footage <webm> --cards <frames_dir> --fonts <dir> --ffmpeg <ffmpeg> --out <mp4>

`plan` time-stretches the narration (TEMPO), lays the 15 script segments end to end and writes
<work>/timeline.json, <work>/narration.wav, <work>/presenter.wav, <work>/cards-jobs.json (for
render_cards.js) and the captions (<work>/captions.srt, <work>/captions.ass). Footage segments use
the windows in FOOTAGE: offsets into the one real take, never sped up or re-staged.

`presenter` uploads presenter.wav (narration audio only: no health data, no footage) and renders
it once on the Meta video's presenter (Sable, avatar_v). It refuses to run if the wallet has
already moved past the cap, and records the wallet before and after.

`compose` builds every segment at 1920x1080 30 fps and burns in the captions. Standard library
only; needs a full ffmpeg (libx264, libass).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.request
import uuid
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPO = 1.06            # narration speed-up (pitch kept), applied before the presenter render
PAD_IN, PAD_OUT = 0.30, 0.25
SR = 48000
FPS = 30
# Footage windows in seconds of the take (clips-1280.json, page@848edca3...webm). Each sits inside
# its recorded clip; the narration starts NARR_AT seconds into the window.
FOOTAGE = {
    "s05": ("s2-checkin-review", 6.30, 20.30, 0.6),
    "s06": ("s3-passport", 24.30, 34.16, 0.3),
    "s07": ("s3b-inclinations", 37.40, 45.19, 0.3),
    "s08": ("s4a-next-step", 46.00, 51.31, 0.4),
    "s09": ("s4b-safety", 59.00, 64.94, 0.3),
    "s10": ("s5b-results", 83.50, 90.56, 0.3),
}
# capture.js stamps clip offsets from its own clock, which starts before the browser does; the
# recorded webm begins TAKE_LAG s later. Measured on this take from six page changes (check-in
# submit, review save, passport, timeline, console, results: 1.0–1.27 s, median 1.15 s).
TAKE_LAG = 1.15
TITLES = {
    "s05": "Check-in and review", "s06": "Passport: evidence thread and a withheld card",
    "s07": "Passport: Inclinations", "s08": "Suggested next step routes to a person",
    "s09": "Safety refusal: crisis hand-off, nothing saved", "s10": "Research console: results",
}
ZOOM = {"title": 1.04, "product": 1.3, "hypothesis": 1.25, "selfcheck": 1.2, "results1": 1.3,
        "results2": 1.25, "outcome": 1.45, "limits": 1.3, "close": 1.35}
# Highest published API rate for an avatar_v render we found (USD per second); used only to
# refuse a render whose worst-case cost would pass the cap.
RATE_HIGH = 0.10
A_W = 1150              # presenter segments: card panel width; the presenter fills the rest


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def silence(sec: float) -> bytes:
    return b"\x00\x00" * int(round(sec * SR))


def pcm(ffmpeg: str, src: Path, dst: Path) -> bytes:
    run([ffmpeg, "-loglevel", "error", "-y", "-i", str(src), "-af", f"atempo={TEMPO}",
         "-ac", "1", "-ar", str(SR), "-sample_fmt", "s16", str(dst)])
    with wave.open(str(dst)) as w:
        return w.readframes(w.getnframes())


def write_wav(path: Path, data: bytes) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(data)


def cues(seg: dict, words: list[dict], t0: float) -> list[tuple[float, float, str]]:
    """Caption cues: one per sentence-ish phrase of the shown text, timed by the spoken words.

    The spoken form ('say') may spell numbers out, so phrases are split on the same punctuation in
    both and matched by order; each cue spans its phrase's first to last spoken word."""
    import re
    split = lambda s: [p.strip() for p in re.split(r"(?<=[.;:?])\s+", s) if p.strip()]
    shown, spoken = split(seg["text"]), split(seg.get("say", seg["text"]))
    assert len(shown) == len(spoken), seg["id"]
    out, wi = [], 0
    for sh, sp in zip(shown, spoken):
        n = len(re.findall(r"[A-Za-z0-9]+(?:[.'’][A-Za-z0-9]+)*", sp))
        ws = words[wi:wi + max(n, 1)]
        wi += n
        if not ws:
            continue
        a, b = ws[0]["start_time"] / TEMPO, ws[-1]["end_time"] / TEMPO
        out.append((t0 + a, t0 + b + 0.15, sh))
    return out


def wrap(text: str, width: int) -> list[str]:
    lines, cur = [], ""
    for w in text.split():
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur); cur = w
        else:
            cur = f"{cur} {w}".strip()
    return lines + [cur]


def ts(t: float, ass: bool = False) -> str:
    h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}" if ass else f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",")


def plan(a: argparse.Namespace) -> None:
    spec = json.loads((HERE / "script.json").read_text())
    take = json.loads(Path(a.clips).read_text())
    clips = {c["id"]: c for c in take["clips"]}
    work = Path(a.work); work.mkdir(parents=True, exist_ok=True)
    narr, pres, t, pt = b"", b"", 0.0, 0.0
    segs, cue_list, jobs = [], [], []
    for seg in spec["segments"]:
        tj = json.loads((Path(a.tts) / f"{seg['id']}.json").read_text())
        speech = pcm(a.ffmpeg, Path(a.tts) / f"{seg['id']}.wav", work / f"{seg['id']}.t.wav")
        sp = len(speech) / 2 / SR
        lead = PAD_IN
        dur = PAD_IN + sp + PAD_OUT
        row = {"id": seg["id"], "section": seg["section"], "kind": seg["kind"], "register": seg["register"],
               "ledger": seg["ledger"], "text": seg["text"], "speech": round(sp, 3)}
        if seg["kind"] == "footage":
            cid, s0, s1, lead = FOOTAGE[seg["id"]]
            c = clips[cid]
            assert c["start"] <= s0 < s1 <= c["end"] + 0.01, (seg["id"], c["start"], c["end"])
            dur = max(s1 - s0, lead + sp + PAD_OUT)
            row.update(clip=cid, take=take["video"], take_from=s0, take_to=s1, url=c["url"],
                       build_sha=take["build_sha"], recorded_at=take["recorded_at"], title=TITLES[seg["id"]])
            path = c["url"].split(".modal.run", 1)[-1] or "/"
            jobs.append({"name": f"frame-{seg['id']}", "card": "footage", "w": 1920, "secs": 0, "params": {
                "title": TITLES[seg["id"]],
                "meta": f"hosted build {take['build_sha'][:7]} · recorded {take['recorded_at'][:10]} · {path}"}})
        else:
            jobs.append({"name": seg["id"], "card": seg["card"], "w": A_W if seg["kind"] == "presenter" else 1920,
                         "secs": 3.6, "params": {"z": str(ZOOM[seg["card"]])}})
        dur = round(dur * FPS) / FPS
        body = silence(lead) + speech
        body += silence(dur - len(body) / 2 / SR)
        narr += body
        if seg["kind"] == "presenter":
            row.update(presenter_from=round(pt, 3), presenter_to=round(pt + dur, 3))
            pres += body; pt += dur
        cue_list += [(s, e, x, seg["kind"]) for s, e, x in cues(seg, tj["words"], t + lead)]
        row.update(start=round(t, 3), end=round(t + dur, 3), dur=round(dur, 3))
        segs.append(row); t += dur
    write_wav(work / "narration.wav", narr)
    write_wav(work / "presenter.wav", pres)
    (work / "cards-jobs.json").write_text(json.dumps(jobs, indent=1))
    (work / "timeline.json").write_text(json.dumps({"total": round(t, 3), "tempo": TEMPO, "presenter_secs": round(pt, 3),
                                                    "voice": spec["voice"], "presenter": spec["presenter"], "segments": segs}, indent=1))
    # SRT: plain cues. ASS: the same cues, placed under the card panel on presenter segments.
    srt = [f"{i}\n{ts(s)} --> {ts(e)}\n" + "\n".join(wrap(x, 64)) + "\n" for i, (s, e, x, k) in enumerate(cue_list, 1)]
    (work / "captions.srt").write_text("\n".join(srt))
    ass = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1920", "PlayResY: 1080", "WrapStyle: 2", "",
           "[V4+ Styles]",
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
           "Style: Cap,Space Grotesk,38,&H00FFFFFF,&H00FFFFFF,&H003A2817,&H003A2817,0,0,0,0,100,100,0,0,3,14,0,2,60,60,46,1",
           "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for s, e, x, k in cue_list:
        width, pos = (52, r"{\an2\pos(575,1032)}") if k == "presenter" else (80, r"{\an2\pos(960,1032)}")
        ass.append(f"Dialogue: 0,{ts(s, True)},{ts(e, True)},Cap,,0,0,0,,{pos}" + r"\N".join(wrap(x, width)))
    (work / "captions.ass").write_text("\n".join(ass) + "\n")
    print(f"total {t:.2f}s, presenter {pt:.2f}s, {len(cue_list)} cues")


# ---------------------------------------------------------------- HeyGen presenter (paid)
def api(method: str, path: str, key: str, body: dict | None = None, raw: bytes | None = None, ctype: str | None = None) -> dict:
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    h = {"X-Api-Key": key}
    if data is not None:
        h["Content-Type"] = ctype or "application/json"
    req = urllib.request.Request(f"https://api.heygen.com{path}", data=data, method=method, headers=h)
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def wallet(key: str) -> float:
    return api("GET", "/v3/users/me", key)["data"]["wallet"]["remaining_balance"]


def presenter(a: argparse.Namespace) -> None:
    key = os.environ["HEYGEN_API_KEY"]
    work = Path(a.work)
    tl = json.loads((work / "timeline.json").read_text())
    log_p = work / "presenter.json"
    log = json.loads(log_p.read_text()) if log_p.exists() else {}
    if not log.get("video_id"):
        quote = tl["presenter_secs"] * RATE_HIGH
        if quote > a.cap_usd:
            raise SystemExit(f"quote USD {quote:.2f} for {tl['presenter_secs']} s exceeds the cap USD {a.cap_usd}: not rendering")
        before = wallet(key)
        b = uuid.uuid4().hex
        f = (work / "presenter.wav").read_bytes()
        raw = (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"presenter.wav\"\r\n"
               f"Content-Type: audio/wav\r\n\r\n").encode() + f + f"\r\n--{b}--\r\n".encode()
        asset = api("POST", "/v3/assets", key, raw=raw, ctype=f"multipart/form-data; boundary={b}")["data"]
        p = tl["presenter"]
        body = {"type": "avatar", "avatar_id": p["avatar_id"], "engine": {"type": p["engine"]},
                "audio_asset_id": asset["asset_id"], "title": "HAC-92 presenter (private)",
                "aspect_ratio": "16:9", "resolution": "1080p"}
        v = api("POST", "/v3/videos", key, body)["data"]
        log = {"asset_id": asset["asset_id"], "video_id": v.get("video_id") or v.get("id"), "request": body,
               "wallet_before_usd": before, "audio_secs": tl["presenter_secs"], "created": time.time()}
        log_p.write_text(json.dumps(log, indent=1))
        print("submitted", log["video_id"])
    while True:
        d = api("GET", f"/v3/videos/{log['video_id']}", key)["data"]
        if d["status"] in ("completed", "failed"):
            break
        time.sleep(20)
    log.update(status=d["status"], duration=d.get("duration"), failure=d.get("failure_message"))
    if d["status"] == "completed":
        urllib.request.urlretrieve(d["video_url"], work / "presenter.mp4")
    log["wallet_after_usd"] = wallet(key)
    log_p.write_text(json.dumps(log, indent=1))
    print(json.dumps({k: log[k] for k in ("status", "duration", "wallet_before_usd", "wallet_after_usd")}))


# ---------------------------------------------------------------- composition
def compose(a: argparse.Namespace) -> None:
    work = Path(a.work)
    tl = json.loads((work / "timeline.json").read_text())
    ff = a.ffmpeg
    parts = []
    tag = "SYNTHETIC DEMO · SIMULATED RESULTS · NOT MEDICAL ADVICE"
    font = f"{a.fonts}/JetBrainsMono.ttf"
    only = set(filter(None, a.only.split(",")))
    for s in tl["segments"]:
        out = work / f"part-{s['id']}.mp4"
        if only and s["id"] not in only:
            parts.append(out)
            continue
        d = s["dur"]
        if s["kind"] == "footage":
            frame = Path(a.cards) / f"frame-{s['id']}" / "f0000.png"
            vf = (f"[1:v]trim={s['take_from'] - TAKE_LAG:.3f}:{s['take_to'] - TAKE_LAG:.3f},setpts=PTS-STARTPTS,fps={FPS},scale=1408:792,"
                  f"tpad=stop_mode=clone:stop_duration={d}[f];[0:v][f]overlay=256:178,trim=0:{d}")
            cmd = [ff, "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(FPS), "-i", str(frame),
                   "-i", a.footage, "-filter_complex", vf]
        else:
            seq = Path(a.cards) / s["id"] / "f%04d.png"
            card = f"[0:v]fps={FPS},tpad=stop_mode=clone:stop_duration={d}"
            if s["kind"] == "presenter":
                # The presenter fills the right column (1920-A_W px), cut from the one render.
                pw = 1920 - A_W
                vf = (f"{card},trim=0:{d}[c];[1:v]trim={s['presenter_from']}:{s['presenter_to']},setpts=PTS-STARTPTS,"
                      f"fps={FPS},scale=-2:1080,crop={pw}:1080,tpad=stop_mode=clone:stop_duration=1[p];"
                      f"[c]pad=1920:1080:0:0:color=0xF1EFE9[cc];[cc][p]overlay={A_W}:0,trim=0:{d},"
                      f"drawbox=x={A_W}:y=0:w=4:h=1080:color=0x17283A:t=fill")
                cmd = [ff, "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(seq),
                       "-i", str(work / "presenter.mp4"), "-filter_complex", vf]
            else:
                vf = f"{card},trim=0:{d}"
                cmd = [ff, "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(seq), "-filter_complex", vf]
        cmd[-1] += (f",drawtext=fontfile={font}:text='{tag}':fontsize=15:fontcolor=0x5B6672:x=w-tw-84:y=26"
                    if s["kind"] != "presenter" else
                    f",drawtext=fontfile={font}:text='{tag}':fontsize=14:fontcolor=0x5B6672:x=84:y=1060-th")
        cmd += ["-t", str(d), "-r", str(FPS), "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "16", str(out)]
        run(cmd)
        parts.append(out)
    lst = work / "parts.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(work / "narration.wav"),
         "-vf", f"subtitles={work / 'captions.ass'}:fontsdir={a.fonts}", "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "slow", "-crf", str(a.crf), "-pix_fmt", "yuv420p", "-r", str(FPS),
         "-c:a", "aac", "-b:a", "128k", "-ar", str(SR), "-ac", "2", "-movflags", "+faststart", "-shortest", a.out])
    print("wrote", a.out)


# ---------------------------------------------------------------- docs (transcript, segment and coverage tables)
# HAC-91 `video-rubric` §3d: the inferred FHDIC rubric (FHDIC publishes no criteria or weights, L41;
# the weights are HAC-91's assumptions). Each criterion: number, name, weight, published/inferred tag,
# the segments that carry it, and how the cut covers it.
RUBRIC = [
    (1, "Problem relevance to the challenge statement (lapse/recovery, sustained change)", 15,
     "published theme; weight assumed", ["s01", "s02", "s12"],
     "s01 frames the lapse (routines break when the week changes) with the no-support baseline over 14-day "
     "episodes; s02 names who keeps a routine going; s12 names lapse recovery as the weakest result. "
     "See the lapse table below."),
    (2, "Technical implementation: working prototype, method soundness", 20,
     "published requirement; weight assumed", ["s03", "s04", "s05", "s06", "s07", "s08", "s09", "s10"],
     "hypothesis and method (s03), self-checks (s04), then the hosted build recorded live (s05–s10)."),
    (3, "Demonstrable value / evidence: sustained outcomes, recovery after lapses, equity", 20,
     "published outcome list; weight assumed", ["s10", "s11", "s12"],
     "results with run, split and n (s10); boundary pass rate and 14-day simulated adherence (s11); "
     "boundary-rule accuracy and the lapse-recovery rubric (s12). All synthetic or simulated. "
     "Equity is a gap (no ledger row)."),
    (4, "Usefulness / impact potential", 15, "inferred", ["s02", "s13"],
     "who it is for (s02); expected outcome, labelled concept and not yet measured (s13)."),
    (5, "Innovation", 10, "inferred", ["s03", "s06", "s07"],
     "a confirmed record plus a step matched to what drives the person (s03); evidence thread (s06); "
     "Inclinations tie each step to an answer (s07)."),
    (6, "Completeness / feasibility / readiness", 10, "inferred", ["s05", "s10", "s14", "s15"],
     "a hosted, working build recorded live, from check-in (s05) to results (s10); the path to real use: "
     "governance gates, clinical reviewer, consented pilot (s14); demo URL and repo (s15)."),
    (7, "Safety, autonomy, inclusion, stated limits and assumptions", 5,
     "published requirement; weight assumed", ["s04", "s05", "s08", "s09", "s14"],
     "nothing saved until the person reviews (s04, s05); hand-off to a person (s08); crisis refusal (s09); "
     "limits (s14). Inclusion (languages, accessibility) is not spoken: gap."),
    (8, "Presentation and demo quality (clarity, fits cap)", 5, "assumption", None,
     "the whole cut: captions burned in, every number names its ledger row, under the 3:00 cap."),
]
# HAC-91 §3e beat budget (seconds) and the segments that make up each beat in this cut.
BEATS = [("Problem", 15, ["s01"]), ("Product", 15, ["s02"]), ("Solution / method", 30, ["s03", "s04"]),
         ("Demo", 55, ["s05", "s06", "s07", "s08", "s09", "s10"]), ("Evidence / results", 35, ["s11", "s12"]),
         ("Expected outcome / impact", 15, ["s13"]), ("Limits", 10, ["s14"]), ("Close", 5, ["s15"])]
# Criteria 1 and 3 turn on lapse -> recovery and sustained change: where the cut covers each, or not.
LAPSE = [
    ("Lapse framed as the problem", ["s01"], "covered", ["L66"],
     "\"Healthy routines break when the week changes\"; no-support baseline 63.7% of days, 150 episodes of 14 days."),
    ("Recovery after a lapse, measured", ["s12"], "covered (weak result, stated as weak)", ["L62"],
     "lapse-recovery rubric passes on 7 (SFT) and 6 (DPO) of 51 check-in prompts, against 81 and 85 of 90 probes."),
    ("Sustained change over time", ["s01", "s11"], "covered, simulated only", ["L66", "L79"],
     "mean adherence over 150 simulated 14-day episodes: 0.840 learned policy, 0.833 best script, 0.637 no support."),
    ("A lapse then a no-blame re-engagement reply, on screen", [], "gap", [],
     "the take shows no lapse check-in and no re-engagement reply. Not fixed this round: it needs a new capture "
     "(and the reply would sit on the weak L62 result)."),
    ("Real-world persistence, retention, equitable benefit", ["s13", "s14"], "gap, stated", ["L73"],
     "nothing is measured on people; s13 says \"not yet measured\", s14 names a consented pilot and a measured "
     "result as next. No ledger row for equity."),
]
SOURCE = {"presenter": "HeyGen presenter (Sable) + card", "card": "card (local render)", "footage": "**real footage**"}


def mmss(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


def docs(a: argparse.Namespace) -> None:
    work, out = Path(a.work), Path(a.out_dir)
    tl = json.loads((work / "timeline.json").read_text())
    segs = {s["id"]: s for s in tl["segments"]}
    pres = json.loads((work / "presenter.json").read_text()) if (work / "presenter.json").exists() else {}
    take = next(s for s in tl["segments"] if s["kind"] == "footage")
    head = (f"Length {mmss(tl['total'])} · 1920×1080 · 30 fps · narration: HeyGen voice *{tl['voice']['voice_name']}* "
            f"(`{tl['voice']['model']}`, ×{tl['tempo']} tempo) · presenter: HeyGen *{tl['presenter']['avatar_name']}* "
            f"(`{tl['presenter']['engine']}`, video `{pres.get('video_id', 'pending')}`) · captions burned in and in "
            f"[`captions.srt`](captions.srt).\n\nFootage: one real Playwright take of the hosted build "
            f"https://supermomo668--daypart-demo-playground.us-east.modal.run, deployed commit `{take['build_sha']}`, "
            f"recorded {take['recorded_at']} (`{take['take']}`; offsets in [`clips-1280.json`](clips-1280.json)). "
            f"Nothing mocked, intercepted, re-staged or sped up.\n")
    t = ["# FHDIC demo video v2: transcript (HAC-92)\n", head,
         "| # | time | section | source | on screen | narration | ledger |", "|---|---|---|---|---|---|---|"]
    for i, s in enumerate(tl["segments"], 1):
        scr = (f"`{s['url'].split('.modal.run', 1)[-1] or '/'}` take {s['take_from']:.2f}–{s['take_to']:.2f} s: {s['title']}"
               if s["kind"] == "footage" else f"card `{s['id']}` ({s['register']})")
        t.append(f"| {i} | {mmss(s['start'])}–{mmss(s['end'])} | {s['section']} | {SOURCE[s['kind']]} | {scr} | {s['text']} | {' '.join(s['ledger'])} |")
    (out / "transcript.md").write_text("\n".join(t) + "\n")
    g = ["# FHDIC demo video v2: segment table (HAC-92)\n",
         "What each second of the cut is made of. *Real footage* is the unedited take of the hosted build. "
         "*HeyGen* is only the presenter in the right-hand column (lip-synced to the narration) and the voice; "
         "every card, chart and caption is rendered locally from [`cards.html`](cards.html) with ledger-row numbers.\n",
         "| # | time | length | real footage | HeyGen | local render |", "|---|---|---|---|---|---|"]
    tot = {"footage": 0.0, "presenter": 0.0, "card": 0.0}
    for i, s in enumerate(tl["segments"], 1):
        tot[s["kind"]] += s["dur"]
        f = (f"{s['clip']} ({s['take_from']:.2f}–{s['take_to']:.2f} s), `{s['build_sha'][:7]}`, {s['url']}"
             if s["kind"] == "footage" else "")
        h = (f"presenter {s['presenter_from']:.2f}–{s['presenter_to']:.2f} s of the render + voice" if s["kind"] == "presenter" else "voice")
        loc = "frame + captions" if s["kind"] == "footage" else f"card `{s['id']}` + captions"
        g.append(f"| {i} | {mmss(s['start'])}–{mmss(s['end'])} | {s['dur']:.1f} s | {f} | {h} | {loc} |")
    g.append(f"\nTotals: real footage {tot['footage']:.1f} s, presenter on screen {tot['presenter']:.1f} s, "
             f"full-frame cards {tot['card']:.1f} s, of {tl['total']:.1f} s.\n")
    (out / "segments.md").write_text("\n".join(g) + "\n")
    def rng(ids: list[str]) -> str:
        return ", ".join(f"{mmss(segs[i]['start'])}–{mmss(segs[i]['end'])}" for i in ids)

    def rows(ids: list[str]) -> str:
        return " · ".join(sorted({r for i in ids for r in segs[i]["ledger"]}, key=lambda x: int(x[1:]))) or "–"

    allids = [s["id"] for s in tl["segments"]]
    c = ["# FHDIC demo video v2: rubric coverage (HAC-92)\n",
         "Mapped to the inferred rubric in HAC-91 `video-rubric` (§3d criteria and weights, §3e time budget), "
         "which landed 2026-11-16. FHDIC publishes no rubric, weights or video rule (L41); the weights are HAC-91's "
         "assumptions, and the tag column says which criteria rest on published text.\n",
         "## Criteria (HAC-91 §3d)\n",
         "| # | criterion | wt | tag | time range | segments | how the cut covers it | evidence rows |",
         "|---|---|---|---|---|---|---|---|"]
    for n, name, wt, tag, ids, how in RUBRIC:
        r = rng(ids) + f" ({sum(segs[i]['dur'] for i in ids):.0f} s)" if ids else f"0:00.0–{mmss(tl['total'])} (whole cut)"
        c.append(f"| {n} | {name} | {wt} | {tag} | {r} | {', '.join(ids) if ids else 'all'} | {how} | "
                 f"{rows(ids) if ids else 'all'} |")
    c += ["\n## Time budget (HAC-91 §3e) vs this cut\n",
          "| beat | budget | actual | Δ | segments | time range |", "|---|---|---|---|---|---|"]
    for name, sec, ids in BEATS:
        act = sum(segs[i]["dur"] for i in ids)
        c.append(f"| {name} | {sec} s | {act:.1f} s | {act - sec:+.1f} s | {', '.join(ids)} | "
                 f"{mmss(segs[ids[0]]['start'])}–{mmss(segs[ids[-1]]['end'])} |")
    c.append(f"| **total** | 180 s (target 175 s) | {tl['total']:.1f} s | {tl['total'] - 180:+.1f} s | | |")
    c += ["\nEvery beat is within about 5 s of its budget. The CTO accepted the residual differences "
          "(HAC-92, 2026-11-16): no re-time and no new render for timing alone.\n",
          "## Lapse → recovery and sustained change (criteria 1 and 3)\n",
          "| what the criterion asks | where | status | what is said or shown | evidence rows |",
          "|---|---|---|---|---|"]
    for what, ids, status, ev, said in LAPSE:
        c.append(f"| {what} | {rng(ids) if ids else '–'} | {status} | {said} | {' · '.join(ev) or '–'} |")
    c.append("\nThe lapse-recovery result (s12, L62) was added in this round, in a card segment (free TTS, local "
             "render); it replaced the trait-recovery line (L75), so the cut stays at about 176 s. "
             "No presenter line changed and there was no new HeyGen spend.")
    (out / "coverage.md").write_text("\n".join(c) + "\n")
    print("wrote transcript.md, segments.md, coverage.md")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan"); p.add_argument("--tts", required=True); p.add_argument("--clips", required=True)
    p.add_argument("--work", required=True); p.add_argument("--ffmpeg", required=True)
    p = sub.add_parser("presenter"); p.add_argument("--work", required=True); p.add_argument("--cap-usd", type=float, default=30.0)
    p = sub.add_parser("compose"); p.add_argument("--work", required=True); p.add_argument("--footage", required=True)
    p.add_argument("--cards", required=True); p.add_argument("--fonts", required=True); p.add_argument("--ffmpeg", required=True)
    p.add_argument("--out", required=True); p.add_argument("--crf", type=int, default=24)
    p.add_argument("--only", default="", help="re-render only these segment parts; the rest are reused")
    p = sub.add_parser("docs"); p.add_argument("--work", required=True); p.add_argument("--out-dir", default=str(HERE))
    a = ap.parse_args()
    {"plan": plan, "presenter": presenter, "compose": compose, "docs": docs}[a.cmd](a)


if __name__ == "__main__":
    main()

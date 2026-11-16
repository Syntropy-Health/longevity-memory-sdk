"""Narration for the v2 video (HAC-92): one HeyGen TTS call per script segment.

Uses heygen-voice-1-turbo-free (no charge) with the Meta video's voice, and keeps the per-word
timestamps for the captions. Only the script text is sent. Standard library only.

    HEYGEN_API_KEY=... python tts.py --out <dir> [--only s01,s02]
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
API = "https://api.heygen.com/v3/models/audio/tts"


def speak(text: str, voice: dict, key: str) -> dict:
    body = json.dumps({"model": voice["model"], "voice_id": voice["voice_id"], "text": text,
                       "with_timestamps": True}).encode()
    for attempt in range(6):
        req = urllib.request.Request(API, data=body, method="POST",
                                     headers={"X-Api-Key": key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)["data"]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            raise SystemExit(f"TTS failed {e.code}: {e.read()[:300]!r}")
    raise SystemExit("TTS: still rate-limited after retries")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    key = os.environ["HEYGEN_API_KEY"]
    spec = json.loads((HERE / "script.json").read_text())
    only = set(filter(None, a.only.split(",")))
    a.out.mkdir(parents=True, exist_ok=True)
    for seg in spec["segments"]:
        if only and seg["id"] not in only:
            continue
        d = speak(seg.get("say", seg["text"]), spec["voice"], key)
        urllib.request.urlretrieve(d["audio_url"], a.out / f"{seg['id']}.wav")
        (a.out / f"{seg['id']}.json").write_text(json.dumps(
            {"id": seg["id"], "text": seg["text"], "say": seg.get("say", seg["text"]), "duration": d["duration"], "words": d["original_words"]}, indent=1))
        print(f"{seg['id']} {d['duration']:.2f}s {len(seg['text'].split())}w")


if __name__ == "__main__":
    main()

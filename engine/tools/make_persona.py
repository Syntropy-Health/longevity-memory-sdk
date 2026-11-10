"""Generate the seeded demo persona (HAC-38 AM-2 D2, addendum G32).

Writes ``daypart/demo/persona_v1.json``: one fictional member's 28 days of plain-language check-ins,
dated ``today - 27`` .. ``today`` (the journal's G9 ``today``). The text is what a person would type;
at app time each check-in is replayed through the real check-in service (extract, then review), so
no value is written around the pipeline. Deterministic: a fixed seed, no clock, no network.

    uv run python tools/make_persona.py          # rewrite the file
    uv run python tools/make_persona.py --check  # exit 1 if the committed file differs
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import sys
from pathlib import Path

from daypart.checkin.journal import DEFAULT_TODAY

OUT = Path(__file__).resolve().parents[1] / "daypart/demo/persona_v1.json"
SEED = 2026
DAYS = 28
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _when(day: dt.date) -> str:
    return f"{MONTHS[day.month - 1]} {day.day}"


def build() -> dict:
    """The persona document (pure: the same dict on every call)."""
    rng = random.Random(SEED)
    first = DEFAULT_TODAY - dt.timedelta(days=DAYS - 1)
    checkins = []
    for i in range(DAYS):
        day = first + dt.timedelta(days=i)
        progress = i / (DAYS - 1)  # a gentle, made-up improvement over the four weeks
        sleep = round(6.1 + 1.2 * progress + rng.uniform(-0.3, 0.3), 1)
        steps = int(round(5200 + 4300 * progress + rng.uniform(-700, 700), -1))
        parts = [f"On {_when(day)} I slept {sleep} hours and walked {steps} steps"]
        if i % 3 == 0:
            parts.append(f"pulse {rng.randint(60, 70)} bpm")
        if i % 7 == 1:
            weight = round(74.2 - 1.4 * progress + rng.uniform(-0.2, 0.2), 1)
            parts.append(f"weight {weight} kg")
            parts.append(f"bp {rng.randint(116, 124)}/{rng.randint(74, 80)} mmhg")
        if i % 4 == 2:
            parts.append(f"exercised {rng.choice((20, 25, 30, 35, 40))} minutes")
        if i == 11:
            parts.append("knee pain 3 out of 10")
        checkins.append({"day": day.isoformat(), "text": "; ".join(parts)})
    return {
        "persona_id": "persona-v1",
        "display_name": "Rowan Ellis",
        "fictional": True,
        "note": "A fictional person made up for this demo by tools/make_persona.py (seed 2026). "
        "Not a real person, patient or record.",
        "member_id": "syn-007",
        "generator": "tools/make_persona.py",
        "seed": SEED,
        "checkins": checkins,
    }


def _text(doc: dict) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if the committed file differs")
    args = ap.parse_args(argv)
    text = _text(build())
    if args.check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("persona ok" if same else f"persona differs: run tools/make_persona.py ({OUT})")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""The Track B numbers in docs/daypart/FHDIC.md are the harness's numbers (track-b-spec)."""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DOC = REPO / "docs" / "daypart" / "FHDIC.md"
METRICS = REPO / "docs" / "daypart" / "results" / "metrics.json"


def _arm() -> dict:
    doc = json.loads(METRICS.read_text(encoding="utf-8"))
    arm = next(a for a in doc["arms"] if a["name"] == "escalation")
    assert arm["status"] == "ok"
    return arm["metrics"]


def _fmt(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.3f}"


def test_results_table_matches_metrics():
    text = DOC.read_text(encoding="utf-8")
    table = text.split("<!-- track-b-results", 1)[1]
    rows = dict(
        (m.group(1), (m.group(2), m.group(3)))
        for m in re.finditer(r"^\| (\w+) \| ([\d.]+|n/a) \| ([\d.]+|n/a) \|$", table, re.M)
    )
    a = _arm()
    for key in ("brier", "ece", "abstention_rate", "precision", "recall"):
        assert rows[key] == (_fmt(a[key]), _fmt(a["base_rate"][key])), key


def test_reliability_and_headline_match_metrics():
    text = DOC.read_text(encoding="utf-8")
    a = _arm()
    for r in a["reliability"]:
        if r["n"]:
            line = f"| {r['lo']:.1f}–{r['hi']:.1f} | {r['n']} | {r['mean_p']:.3f} | {r['frac_positive']:.3f} |"
            assert line in text, line
    prose = " ".join(text.split())  # prose wraps across lines
    assert f"({a['n']} assessments, {a['positives']} positive, prevalence {a['prevalence']:.3f})" in prose
    assert f"training prevalence ({a['base_rate']['p']:.3f})" in prose
    beats = a["beats_base_rate"]["brier"] or a["beats_base_rate"]["ece"]
    assert ("**no better than a constant base-rate predictor**" in prose) == (not beats)
    assert "nothing here is clinically validated" in prose.lower()

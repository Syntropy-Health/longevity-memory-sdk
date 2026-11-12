"""HAC-86: the submission deck served at /deck by the demo app.

The deck is a static page (daypart/demo/deck, written by docs/daypart/submission/deck/build_web_deck.py).
These checks hold the acceptance lines the build can test without a browser: the route and its assets,
the top-down section order, a ledger row behind every slide, no caveat labels and a short body.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from daypart.demo.app import create_app  # noqa: E402

LEDGER = Path(__file__).resolve().parents[3] / "docs" / "daypart" / "submission" / "evidence-ledger.md"
SECTIONS = ["problem", "problem", "design", "design", "design", "technical", "technical", "technical", "technical", "next"]
# The board removed these from the visual deck (HAC-86 acceptance 3); the ledger and appendix keep them.
CAVEATS = ("SIMULATED ·", "Template pending", "TEMPLATE PENDING", "Not tested with people", "One seed only",
           "not written by people", "Synthetic / simulated results", "CONCEPT")
# Claims the build does not support (acceptance 4).
UNSUPPORTED = re.compile(r"clinically (validated|proven)|validated with (patients|people)|tested with (patients|people)|"
                         r"improves (health|outcomes)", re.I)
TAG = re.compile(r"<[^>]+>")


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


@pytest.fixture(scope="module")
def page(client) -> str:
    r = client.get("/deck")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    return r.text


def _slides(page: str) -> list[str]:
    return re.findall(r'<section class="slide.*?</section>', page, re.S)


def test_deck_route_and_assets(client, page):
    for path, media in [("/deck/deck.css", "text/css"), ("/deck/deck.js", "text/javascript")]:
        r = client.get(path)
        assert r.status_code == 200 and r.headers["content-type"].startswith(media)
    for src in set(re.findall(r'src="(/deck/screens/[^"]+)"', page)):
        r = client.get(src)
        assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg", src
    assert client.get("/deck/../app.py").status_code == 404
    assert client.get("/deck/nope.js").status_code == 404
    r = client.get("/deck/", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == "/deck"


def test_top_down_sections_and_headline_first(page):
    slides = _slides(page)
    assert [re.search(r'data-section="(\w+)"', s).group(1) for s in slides] == SECTIONS
    for s in slides:
        # the headline is the first text on the slide after the section kicker and brand
        body = s.split('<span class="brand">', 1)[1]
        assert re.search(r"</span></span></div><h[12]>[^<]{10,}</h[12]>", body), s[:200]


def test_every_slide_names_existing_ledger_rows(page):
    ledger = LEDGER.read_text(encoding="utf-8")
    rows = set(re.findall(r"^\| (L\d+|P\d+) \|", ledger, re.M))
    for s in _slides(page):
        named = re.search(r'data-ledger="([^"]+)"', s).group(1).split()
        assert named, s[:120]
        assert set(named) <= rows, set(named) - rows
        assert 'class="notes"' in s and "Ledger rows:" in s
    for figure in re.findall(r'<svg class="d"[^>]*>', page):
        assert set(re.search(r'data-ledger="([^"]+)"', figure).group(1).split()) <= rows


def test_no_caveat_labels_and_no_unsupported_claims(page):
    visible = TAG.sub(" ", re.sub(r'<aside class="notes".*?</aside>', "", page, flags=re.S))
    for c in CAVEATS:
        assert c not in visible, c
    assert not UNSUPPORTED.search(visible)


def test_body_text_is_short(page):
    for lead in re.findall(r'<p class="lead">([^<]*)</p>', page):
        assert len(lead.split()) <= 25, lead


def test_links_to_demo_and_repo(page):
    assert 'href="https://supermomo668--daypart-demo-playground.us-east.modal.run"' in page
    assert 'href="https://github.com/Syntropy-Health/longevity-memory-sdk"' in page

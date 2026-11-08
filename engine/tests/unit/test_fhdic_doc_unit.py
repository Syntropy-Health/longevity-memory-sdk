"""AIR-321: the FHDIC Challenge 09 submission page states every limitation and has no dead links."""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
DOC = REPO / "docs" / "daypart" / "FHDIC.md"
README = REPO / "README.md"

# AC5: each statement must appear verbatim (case-insensitive) on the page.
REQUIRED_STATEMENTS = [
    "synthetic data only",
    "175 train",
    "25 held-out",
    "simulator-only results",
    "no clinical or safety validation",
    "no phi",
    "no medical, diagnostic, dosing or treatment advice",
    "no malaffi/sahatna integration",
    "no consumer ui",
    "grpo, the reward model and the jev question library are designed, not built",
    "meta eligibility is unconfirmed and out of scope here",
    "python 3.12",
    "uv",
    "pinned lhm",
    "modal",
    "meta-models/muse-glimmer-30b",
    "muse spark (optional)",
]

# AC1: index rows, in the order the challenge lists its deliverables.
INDEX_ROWS = [
    "Prototype",
    "Demo access",
    "Technical documentation",
    "Assumptions, dependencies, limitations",
    "Training record",
    "Track B",
    "Track C",
]

LINK = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def _text() -> str:
    return DOC.read_text(encoding="utf-8")


def _relative_links(text: str) -> list[str]:
    out = []
    for target in LINK.findall(text):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
            continue
        out.append(target.split("#", 1)[0])
    return out


@pytest.mark.parametrize("statement", REQUIRED_STATEMENTS)
def test_required_statement_present(statement):
    assert statement in _text().lower()


def test_every_relative_link_resolves():
    links = _relative_links(_text())
    assert links, "page has no relative links"
    missing = [t for t in links if not (DOC.parent / t).resolve().exists()]
    assert missing == []


def test_relative_links_stay_inside_repo():
    for target in _relative_links(_text()):
        assert (DOC.parent / target).resolve().is_relative_to(REPO)


def test_index_comes_first_and_lists_every_deliverable():
    text = _text()
    first_h2 = re.search(r"^## (.+)$", text, re.M)
    assert first_h2 and first_h2.group(1).strip().lower().startswith("index")
    index = text[first_h2.end() : text.index("\n## ", first_h2.end())]
    for row in INDEX_ROWS:
        assert re.search(rf"^\|\s*\**{re.escape(row)}\**\s*\|", index, re.M), row
    assert "prepared by agents" in index.lower()
    assert "the principal submits" in index.lower()


def test_track_b_is_placeholder_until_cto_updates_it():
    row = next(l for l in _text().splitlines() if re.match(r"^\|\s*\**Track B", l))
    assert "in progress (AIR-319 child 2)" in row or "built" in row.lower()


def test_track_c_names_both_passports_and_their_tests():
    text = _text()
    assert "Pattern passport" in text and "Health Clone Passport" in text
    for path in (
        "engine/tests/sealed/test_passport.py",
        "engine/tests/unit/test_passport_unit.py",
        "engine/tests/unit/test_passport_view_unit.py",
    ):
        assert path in text
        assert (REPO / path).exists()


def test_training_numbers_match_readme():
    """AC4: no new numbers. Every table row of the training record is copied from the README."""
    text = _text()
    start = text.index("## Training record")
    section = text[start : text.index("\n## ", start + 1)]
    readme = README.read_text(encoding="utf-8")
    rows = [l for l in section.splitlines() if l.startswith("|") and not set(l) <= set("|-: ")]
    assert len(rows) >= 10
    for row in rows:
        assert row in readme, row


def test_readme_links_to_page():
    readme = README.read_text(encoding="utf-8")
    assert "## FHDIC Challenge 09" in readme
    assert "(docs/daypart/FHDIC.md)" in readme

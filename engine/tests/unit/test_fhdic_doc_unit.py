"""AIR-321: the FHDIC Challenge 09 submission page states every limitation and has no dead links."""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
DOC = REPO / "docs" / "daypart" / "FHDIC.md"
README = REPO / "README.md"

# AC5: each limitation and dependency is its own bullet in the limitations section, so a phrase
# that only appears elsewhere (a `uv run` command, a modal.run URL) does not count.
LIMITATIONS_HEADING = "## Assumptions, dependencies, limitations"
REQUIRED_BULLETS = [
    "synthetic data only: 175 train / 25 held-out profiles",
    "simulator-only results",
    "no clinical or safety validation",
    "no phi",
    "no medical, diagnostic, dosing or treatment advice",
    "no malaffi/sahatna integration",
    "no consumer ui",
    "grpo, the reward model and the jev question library are designed, not built",
    "meta eligibility is unconfirmed and out of scope here",
    "python 3.12",
    "uv,",
    "pinned lhm",
    "modal",
    "hugging face meta-models/muse-glimmer-30b",
    "muse spark (optional)",
]
# Wording the page must carry so it does not overstate what the code guarantees (QG F1).
REQUIRED_CAVEATS = ["not a privacy control"]

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


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    nxt = text.find("\n## ", start + len(heading))
    return text[start : nxt if nxt != -1 else len(text)]


def _bullets(section: str) -> list[str]:
    return [l[2:].replace("`", "").strip().lower() for l in section.splitlines() if l.startswith("- ")]


def _missing_bullets(text: str) -> list[str]:
    if LIMITATIONS_HEADING not in text:
        return list(REQUIRED_BULLETS)
    bullets = _bullets(_section(text, LIMITATIONS_HEADING))
    return [b for b in REQUIRED_BULLETS if not any(x.startswith(b) for x in bullets)]


@pytest.mark.parametrize("statement", REQUIRED_BULLETS)
def test_required_statement_is_a_limitations_bullet(statement):
    assert statement not in _missing_bullets(_text())


@pytest.mark.parametrize("caveat", REQUIRED_CAVEATS)
def test_required_caveat_in_limitations(caveat):
    assert caveat in _section(_text(), LIMITATIONS_HEADING).lower()


def test_statements_elsewhere_on_page_do_not_count():
    """QG F4: `uv run`, a modal.run URL or "Python 3.12+" in How to run must not satisfy AC5."""
    page = (
        "## How to run\n\nRequires Python 3.12+ and uv. `uv run modal run x` on modal.run, "
        "meta-models/Muse-Glimmer-30B.\n\n" + LIMITATIONS_HEADING + "\n\n- Pinned LHM.\n"
    )
    missing = _missing_bullets(page)
    for dep in ("python 3.12", "uv,", "modal", "hugging face meta-models/muse-glimmer-30b"):
        assert dep in missing


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
        assert re.search(rf"^\|\s*\**{re.escape(row)}\b", index, re.M), row
    assert "prepared by agents" in index.lower()
    assert "the principal submits" in index.lower()


def test_track_b_is_placeholder_until_cto_updates_it():
    """AC6: the placeholder, or after the CTO's update "Built" or "Not built" (then a limitation)."""
    text = _text()
    rows = [l for l in text.splitlines() if re.match(r"^\|\s*\**Track B\b", l)]
    assert len(rows) == 1
    status = rows[0].strip().strip("|").split("|")[-1].strip()
    assert status == "in progress (AIR-319 child 2)" or re.match(r"^(Built|Not built)\b", status), status
    if status.startswith("Not built"):
        assert any("track b" in b for b in _bullets(_section(text, LIMITATIONS_HEADING)))


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

"""HAC-64 submission package: form responses, deck outline and technical appendix.

The form answers are pasted into a form with character limits, so every answer must state its
own length, and that length must be true and within the limit. Every claim an answer, a slide or
the appendix makes points to a row of ``evidence-ledger.md`` (whose rows the R11 suite already
checks), so a ledger id that does not exist fails here. The brief's guardrails are checked as
text: conflict of interest is never "None", no wearable or sensor is implied, the tagline is the
owner's verbatim, and framework names appear only in the appendix.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
PACK = REPO / "docs" / "daypart" / "submission"
NEW_FILES = ("form-responses.md", "technical-appendix.md", "deck-outline.md")

FIELDS = (
    "Challenge",
    "Solution summary",
    "Solution stage",
    "Built during challenge",
    "Technology type",
    "Prototype link",
    "Deck",
    "Conflict of interest",
    "Software or hardware",
    "Video link",
)
LIMITS = {"Solution summary": 2000, "Built during challenge": 1500, "Prototype link": 1024}
TAGLINE = (
    "Untangling curse of dimensionality in small cohort study of biometrics in the lens of "
    "clinical importance"
)
# Libraries, platforms and model names: the appendix may name them, the form and deck may not.
FRAMEWORKS = (
    "fastapi", "streamlit", "modal", "trl", "peft", "transformers", "pytorch", "torch",
    "playwright", "axe", "aviary", "pydantic", "uvicorn", "muse", "hugging face", "lhm",
)
LEDGER_ID_RE = re.compile(r"\bL(\d+)\b")
SECTION_RE = re.compile(r"^## (.+)$", re.M)
ANSWER_RE = re.compile(r"```text\n(.*?)\n```", re.S)
COUNT_RE = re.compile(r"^\*\*Characters:\*\* (\d+) / (\d[\d,]*|no limit)", re.M)


def _text(name: str) -> str:
    return (PACK / name).read_text(encoding="utf-8")


def _sections(text: str) -> dict[str, str]:
    heads = list(SECTION_RE.finditer(text))
    return {
        m.group(1).strip(): text[m.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        for i, m in enumerate(heads)
    }


def _answers() -> dict[str, tuple[str, str]]:
    """Field -> (answer text, the whole section)."""
    out = {}
    for head, body in _sections(_text("form-responses.md")).items():
        m = re.match(r"Field \d+: (.+)", head)
        if not m:
            continue
        ans = ANSWER_RE.search(body)
        assert ans, f"{head}: no ```text answer block"
        out[m.group(1).strip()] = (ans.group(1), body)
    return out


def _ledger_ids() -> set[int]:
    return {int(m.group(1)) for m in re.finditer(r"^\| L(\d+) \|", _text("evidence-ledger.md"), re.M)}


def _negated(low: str, start: int) -> bool:
    return bool(re.search(r"\b(no|not|never|without|nor)\b", low[max(0, start - 40):start]))


@pytest.mark.parametrize("name", NEW_FILES)
def test_every_new_file_exists_and_is_not_empty(name: str) -> None:
    assert (PACK / name).is_file(), name
    assert _text(name).strip(), name


def test_form_has_one_section_per_field_in_order() -> None:
    assert list(_answers()) == list(FIELDS)


@pytest.mark.parametrize("field", FIELDS)
def test_each_answer_states_its_true_length_within_the_limit(field: str) -> None:
    answer, body = _answers()[field]
    m = COUNT_RE.search(body)
    assert m, f"{field}: no '**Characters:** n / limit' line"
    assert int(m.group(1)) == len(answer), f"{field}: states {m.group(1)}, is {len(answer)}"
    if field in LIMITS:
        assert m.group(2).replace(",", "") == str(LIMITS[field]), f"{field}: wrong limit"
        assert len(answer) <= LIMITS[field], f"{field}: {len(answer)} > {LIMITS[field]}"


@pytest.mark.parametrize("field", FIELDS)
def test_each_answer_names_its_ledger_rows_and_they_exist(field: str) -> None:
    _, body = _answers()[field]
    line = re.search(r"^\*\*Ledger rows:\*\* (.+)$", body, re.M)
    assert line, f"{field}: no '**Ledger rows:**' line"
    ids = {int(i) for i in LEDGER_ID_RE.findall(line.group(1))}
    if "none" not in line.group(1).lower():
        assert ids, f"{field}: no ledger id"
    assert ids <= _ledger_ids(), f"{field}: unknown ledger rows {sorted(ids - _ledger_ids())}"


def test_conflict_of_interest_is_owner_input_and_never_none() -> None:
    answer, _ = _answers()["Conflict of interest"]
    assert "owner input required" in answer.lower()
    assert not re.search(r"(^|\W)none(\W|$)", answer, re.I), "never default to 'None'"


def test_stage_and_technology_type_are_as_the_brief_sets_them() -> None:
    answers = _answers()
    assert answers["Solution stage"][0].startswith("Prototype")
    assert "synthetic" in answers["Solution stage"][0].lower()
    tech = answers["Technology type"][0].lower()
    assert "software" in tech and "ml/ai agent" in tech


def test_no_answer_implies_a_wearable_or_sensor() -> None:
    for field, (answer, _) in _answers().items():
        low = answer.lower()
        for word in ("wearable", "sensor"):
            for m in re.finditer(word, low):
                assert _negated(low, m.start()), f"{field}: '{word}' without a negation"


def test_the_tagline_is_verbatim_and_framed_as_an_aim() -> None:
    text = _text("form-responses.md")
    assert TAGLINE in text
    assert "Syntropy" in text
    low = text.lower()
    for claim in ("solves the curse", "solved the curse", "clinical importance is established",
                  "clinically important results"):
        assert claim not in low, claim


def test_built_during_challenge_separates_foundation_from_challenge_work_with_dates() -> None:
    answer, _ = _answers()["Built during challenge"]
    assert "2026-11-02" in answer and "2026-11-03" in answer
    assert re.search(r"pre-existing|existing", answer, re.I)


@pytest.mark.parametrize("name", ("form-responses.md", "deck-outline.md"))
def test_framework_names_appear_only_in_the_appendix(name: str) -> None:
    # A URL is an address, not exposition: the hosted demo's host name contains "modal".
    low = re.sub(r"https?://\S+", " ", _text(name)).lower()
    for fw in FRAMEWORKS:
        assert not re.search(rf"\b{re.escape(fw)}\b", low), f"{name}: names '{fw}'"


def test_appendix_names_its_frameworks() -> None:
    low = _text("technical-appendix.md").lower()
    assert "fastapi" in low and "modal" in low


def test_appendix_covers_the_brief() -> None:
    low = _text("technical-appendix.md").lower()
    for topic in ("observation semantics", "adaptation", "rigour", "safety and privacy",
                  "data sources and rights", "dependencies", "path to clinical validation",
                  "grpo", "not built", "leakage", "seed", "denominator", "failure slice"):
        assert topic in low, topic


def test_appendix_names_a_real_blocked_case_with_its_trace() -> None:
    text = _text("technical-appendix.md")
    assert '"status": "handoff"' in text
    assert "real_input_refused" in text


@pytest.mark.parametrize("name", NEW_FILES)
def test_every_ledger_id_cited_exists(name: str) -> None:
    cited = {int(i) for i in LEDGER_ID_RE.findall(_text(name))}
    assert cited, f"{name}: cites no ledger row"
    assert cited <= _ledger_ids(), f"{name}: unknown ledger rows {sorted(cited - _ledger_ids())}"


def test_deck_outline_has_eight_slides_each_with_message_rows_and_illustration() -> None:
    slides = {h: b for h, b in _sections(_text("deck-outline.md")).items() if h.startswith("Slide ")}
    assert [h.split(":")[0] for h in slides] == [f"Slide {i}" for i in range(1, 9)]
    for head, body in slides.items():
        for label in ("**Message:**", "**Ledger rows:**", "**Illustration:**"):
            assert label in body, f"{head}: no {label}"


def test_form_names_the_hosted_commit_it_describes() -> None:
    text = _text("form-responses.md")
    assert re.search(r"\b[0-9a-f]{7,40}\b", text)
    assert "CI run" in text


def test_ledger_keeps_synthetic_and_clinical_evidence_apart_and_lists_pending() -> None:
    text = _text("evidence-ledger.md")
    assert "## Clinical evidence" in text
    assert "## Pending or omitted claims" in text
    assert "*reported*" in text

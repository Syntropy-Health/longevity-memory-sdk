"""R11 submission pack (A&D §4.11): T11.1, T11.2 and the T5.6 README notice.

Every claim in ``evidence-ledger.md`` names a committed artefact (a repo path that exists) or an
assumption id defined in ``assumptions-limits.md`` (SC7). ``outcomes.md`` is generated from
``lab_rows()`` and never hand-typed, so it must equal a fresh render byte for byte (T11.2).
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

from daypart.demo.lab import NOT_RECORDED, PROPOSED, PROVENANCE_MISMATCH, LabRow, LabTable, Split, lab_rows
from daypart.memory.registry import LOINC_NOTICE

REPO = Path(__file__).resolve().parents[3]
PACK = REPO / "docs" / "daypart" / "submission"
RENDERER = REPO / "engine" / "tools" / "render_outcomes.py"
PACK_FILES = (
    "README.md",
    "architecture.md",
    "evidence-ledger.md",
    "outcomes.md",
    "assumptions-limits.md",
    "organiser-rules.md",
    "real-input-pathway.md",
)
PLAYGROUND = "https://supermomo668--daypart-demo-playground.us-east.modal.run"
DASHBOARD = "https://supermomo668--daypart-demo-dashboard.us-east.modal.run"
# Every URL host the public pack may name: the existing demo hosts (A8, no new host), the repo,
# the organiser page, the licences and the evidence sources. Anything else (an internal host,
# localhost, a tracker) fails, because the repo is public.
ALLOWED_HOSTS = {
    "supermomo668--daypart-demo-playground.us-east.modal.run",
    "supermomo668--daypart-demo-dashboard.us-east.modal.run",
    "github.com",
    "hack2skill.com",
    "loinc.org",
    "www.mozilla.org",
    "www.apache.org",
    "medlineplus.gov",
    "www.nhlbi.nih.gov",
    "www.who.int",
}
ASSUMPTION_RE = re.compile(r"\bASSUMPTION\s+((?:D-)?A\d+|O\d+)\b")
LEDGER_ROW_RE = re.compile(r"^\|\s*(L\d+)\s*\|(.*)\|\s*$")
CODE_SPAN_RE = re.compile(r"`([^`]+)`")
LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
URL_RE = re.compile(r"https?://[^\s)>`\"']+")


def _load_renderer():
    spec = importlib.util.spec_from_file_location("render_outcomes", RENDERER)
    assert spec and spec.loader, RENDERER
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("render_outcomes", mod)
    spec.loader.exec_module(mod)
    return mod


def _text(name: str) -> str:
    return (PACK / name).read_text(encoding="utf-8")


def _ledger_rows() -> list[tuple[str, str, str]]:
    rows = []
    for line in _text("evidence-ledger.md").splitlines():
        m = LEDGER_ROW_RE.match(line.strip())
        if not m:
            continue
        cells = [c.strip() for c in m.group(2).split("|")]
        assert len(cells) == 2, f"{m.group(1)}: expected | id | claim | evidence |, got {line!r}"
        rows.append((m.group(1), cells[0], cells[1]))
    return rows


def _defined_assumptions() -> set[str]:
    # An id is defined by a bullet that starts with it in bold: "- **A1.** ..." / "- **D-A2.** ...".
    return set(re.findall(r"^- \*\*((?:D-)?A\d+|O\d+)\.\*\*", _text("assumptions-limits.md"), re.M))


def _repo_path(span: str) -> Path | None:
    """A code span that names a repo path (has a slash or a known top-level file), else None."""
    path = span.split("#", 1)[0].split(":", 1)[0].strip()
    if " " in path or path.startswith(("http", "/", "GET", "POST")):
        return None
    if "/" in path or path in {"ATTRIBUTION.md", "README.md", "LICENSE", "NOTICE"}:
        return REPO / path
    return None


# --- T11.1 ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", PACK_FILES)
def test_t11_1_every_pack_file_exists_and_is_not_empty(name: str) -> None:
    assert (PACK / name).is_file(), name
    assert _text(name).strip(), f"{name} is empty"


def _ledger_table_body_lines(text: str) -> list[str]:
    """Every table line except the header and separator rows (QG P4.1 K2)."""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|") or re.fullmatch(r"\|[\s|:-]+\|?", s) or s.startswith("| id |"):
            continue
        out.append(s)
    return out


def test_t11_1_every_ledger_table_row_parses() -> None:
    # A row the parser skips is a row nobody checks: no trailing pipe, "l8" or "L8a" must fail.
    for line in _ledger_table_body_lines(_text("evidence-ledger.md")):
        assert LEDGER_ROW_RE.match(line), f"unparseable ledger row: {line!r}"


def test_t11_1_ledger_ids_are_contiguous() -> None:
    rows = _ledger_rows()
    assert len(rows) >= 20, "the ledger must trace the pack's claims, not a sample"
    ids = [r[0] for r in rows]
    assert ids == [f"L{i}" for i in range(1, len(ids) + 1)], "ledger ids must run L1..Ln with no gap"


@pytest.mark.parametrize("bad", [
    "| L8 | claim | `ATTRIBUTION.md`",
    "| l8 | claim | `ATTRIBUTION.md` |",
    "| L8a | claim | `ATTRIBUTION.md` |",
])
def test_t11_1_malformed_rows_are_caught(bad: str) -> None:
    assert _ledger_table_body_lines(bad) == [bad]
    assert not LEDGER_ROW_RE.match(bad)


def test_t11_1_every_ledger_row_resolves_or_is_an_assumption() -> None:
    defined = _defined_assumptions()
    for lid, claim, evidence in _ledger_rows():
        assert claim, f"{lid}: empty claim"
        paths = [p for s in CODE_SPAN_RE.findall(evidence) if (p := _repo_path(s)) is not None]
        tags = ASSUMPTION_RE.findall(evidence)
        assert paths or tags, f"{lid}: no committed artefact path and no ASSUMPTION tag"
        for p in paths:
            assert p.exists(), f"{lid}: {p.relative_to(REPO)} does not exist"
        for t in tags:
            assert t in defined, f"{lid}: ASSUMPTION {t} is not defined in assumptions-limits.md"


def test_t11_1_a_missing_path_or_unknown_assumption_would_fail(tmp_path: Path) -> None:
    # Guard the checker itself: a made-up path does not resolve and a tag needs a definition.
    assert _repo_path("engine/daypart/no_such_module.py") is not None
    assert not _repo_path("engine/daypart/no_such_module.py").exists()  # type: ignore[union-attr]
    assert _repo_path("`not a path`") is None
    assert "A99" not in _defined_assumptions()
    assert ASSUMPTION_RE.findall("ASSUMPTION D-A2 and ASSUMPTION O1") == ["D-A2", "O1"]


def test_assumptions_cover_the_pvr_and_design_assumptions() -> None:
    defined = _defined_assumptions()
    for i in range(1, 10):
        assert f"A{i}" in defined, f"PVR assumption A{i} missing"
        assert f"D-A{i}" in defined, f"design assumption D-A{i} missing"
    text = _text("assumptions-limits.md").lower()
    for phrase in ("synthetic", "no clinical use", "not a privacy control"):
        assert phrase in text, phrase


# --- T11.2 ----------------------------------------------------------------------------------------


def test_t11_2_outcomes_equals_the_regenerated_table() -> None:
    ro = _load_renderer()
    assert _text("outcomes.md") == ro.render(lab_rows()), (
        "outcomes.md is stale: run `uv run python tools/render_outcomes.py` from engine/"
    )


def test_t11_2_render_is_deterministic_and_carries_every_row() -> None:
    ro = _load_renderer()
    table = lab_rows()
    out = ro.render(table)
    assert out == ro.render(lab_rows())
    for row in table.rows:
        assert f"| {row.row} |" in out, row.row
        if row.run_id:
            assert row.run_id in out
    assert table.footer in out


def test_t11_2_missing_fields_render_not_recorded_and_no_number(tmp_path: Path) -> None:
    ro = _load_renderer()
    out = ro.render(lab_rows(tmp_path))  # no committed artefacts at all
    model_lines = [ln for ln in out.splitlines() if ln.startswith(("| base |", "| sft |", "| dpo |"))]
    assert len(model_lines) == 3
    for ln in model_lines:
        # base has no run id ("not recorded"); sft/dpo have no training.json to match, so they are
        # a provenance mismatch. Either way no number is shown ("sha256" is a label, not a value).
        assert NOT_RECORDED in ln
        assert not re.search(r"\d", ln.split("|", 2)[2].replace("sha256", "")), f"a number with no source: {ln}"
    assert sum(PROVENANCE_MISMATCH in ln for ln in model_lines) == 2
    grpo = next(ln for ln in out.splitlines() if ln.startswith("| grpo |"))
    assert PROPOSED in grpo


def test_t11_2_mismatch_row_carries_no_number_and_pipes_are_escaped() -> None:
    ro = _load_renderer()
    table = LabTable(
        rows=(
            LabRow(row="sft", kind="model", status=PROVENANCE_MISMATCH, run_id="r|1",  # type: ignore[arg-type]
                   split=Split(prompt_set_version="p", data_sha256="abc"), failures=7,
                   metrics={"boundary_pass_rate": 0.5}),
        ),
        member_failure_count=None,
        i1_passed=None,
    )
    out = ro.render(table)
    line = next(ln for ln in out.splitlines() if ln.startswith("| sft |"))
    assert PROVENANCE_MISMATCH in line
    assert r"r\|1" in line
    assert "0.5" not in line and "| 7 |" not in line
    assert f"I1 builder check: {NOT_RECORDED}" in out


def test_render_cli_writes_and_checks(tmp_path: Path) -> None:
    ro = _load_renderer()
    out = tmp_path / "outcomes.md"
    assert ro.main(["--output", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == ro.render(lab_rows())
    assert ro.main(["--check", "--output", str(out)]) == 0
    out.write_text("hand-typed\n", encoding="utf-8")
    assert ro.main(["--check", "--output", str(out)]) == 1


# --- README, T5.6 and the rest of the pack --------------------------------------------------------


def test_t5_6_readme_carries_the_loinc_notice_and_licence_link() -> None:
    readme = _text("README.md")
    assert LOINC_NOTICE in readme
    assert "https://loinc.org/license/" in readme


def test_readme_names_the_existing_demo_urls_and_the_challenge_framing() -> None:
    readme = _text("README.md")
    workflow = (REPO / ".github" / "workflows" / "engine.yml").read_text(encoding="utf-8")
    for url in (PLAYGROUND, DASHBOARD):
        assert url in readme
        assert url in workflow, "the pack must name the hosts CI deploys, not a new one"
    # A1 as answered by the board; titles as the organiser writes them (HAC-34 research).
    assert "Sustaining Healthy Behaviors" in readme
    assert "Precision Prevention and Screening" in readme
    assert "Closing the Screening-to-Care Loop" in readme


def test_architecture_carries_the_blueprint_diagrams() -> None:
    arch = _text("architecture.md")
    assert arch.count("```mermaid") >= 2
    assert "flowchart" in arch and "sequenceDiagram" in arch


def test_organiser_rules_checklist_states_the_cutoff_and_a_status_per_rule() -> None:
    text = _text("organiser-rules.md")
    assert "2026-11-20 18:29 UTC" in text
    # An item is its "- [ ]" line plus any indented continuation lines.
    items = re.findall(r"^- \[( |x)\] (.+(?:\n  .+)*)", text, re.M)
    assert len(items) >= 6
    for _, item in items:
        assert re.search(r"\*\*(met|unverified|not published|open)\*\*", item), item


def test_real_input_pathway_points_to_the_gated_doc() -> None:
    assert "](../real-input-pathway.md)" in _text("real-input-pathway.md")


@pytest.mark.parametrize("name", PACK_FILES)
def test_relative_links_resolve(name: str) -> None:
    for target in LINK_RE.findall(_text(name)):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path = (PACK / target.split("#", 1)[0]).resolve()
        assert path.exists(), f"{name}: dead link {target}"


@pytest.mark.parametrize("name", PACK_FILES)
def test_no_url_outside_the_public_allow_list(name: str) -> None:
    for url in URL_RE.findall(_text(name)):
        host = urlparse(url.rstrip(".,;")).hostname
        assert host in ALLOWED_HOSTS, f"{name}: {url} names a host outside the allow-list"


@pytest.mark.parametrize("name", PACK_FILES)
def test_no_overclaiming_copy(name: str) -> None:
    low = _text(name).lower()
    # AM-1 / D-A6: nobody clinically reviewed anything; demo mode is on (R1).
    for phrase in ("clinically reviewed", "vetted sources", "clinically validated"):
        for m in re.finditer(re.escape(phrase), low):
            before = low[max(0, m.start() - 12):m.start()]
            assert re.search(r"\b(not|never|no)\b", before), f"{name}: unqualified '{phrase}'"

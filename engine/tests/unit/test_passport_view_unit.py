"""HAC-38 P2 task 7: the Health Clone Passport view (A&D §4.4, §4.5; AM-1 ranges).

Covers T6.1-T6.6, T5.4 and SC9 for the passport: observation cards show the recorded value only,
each card's evidence thread has five linked steps, an explanation shows only when sourced, safe and
ready, and a sourced reference range sits beside a ready value with no judgement. Synthetic only.
"""

import asyncio
import datetime as dt
import re

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from daypart.demo.app import create_app
from daypart.evidence.registry import load_evidence
from daypart.membrane import dsl
from daypart.memory.registry import LOINC_VERSION, REVIEWER_STATUS, load_registry, slice_ontology
from daypart.passport.constants import WITHHELD_MESSAGE
from daypart.passport.view import (
    NOT_ENOUGH_EVIDENCE,
    STEP_NAMES,
    HealthClonePassport,
    boundary_run_id,
    health_clone_passport,
    journal_as_of,
)
from daypart.simmember.trajectory import START_DATE
from syntropy.lhm.metrics.claims import assert_narration_safe

TODAY = START_DATE.date() + dt.timedelta(days=28)
RUN_ID = "hac28-20261105T081951Z/daypart-dpo-947059e60fcf"


@pytest.fixture(scope="module")
def client():
    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("DAYPART_REAL_INPUT", raising=False)
        with TestClient(create_app(cohort_seed=0)) as c:
            yield c


def _journal(client, member_id="syn-001"):
    r = client.post("/api/journals", json={"member_id": member_id})
    assert r.status_code == 201, r.text
    return r.json()["journal_id"]


def _save(client, jid, text, decisions=None):
    ck = client.post("/api/checkins", json={"journal_id": jid, "text": text})
    assert ck.status_code == 201, ck.text
    body = ck.json()
    if decisions is None:
        decisions = [{"proposal_id": p["proposal_id"], "action": "confirm"} for p in body["proposals"]]
    r = client.post(f"/api/checkins/{body['checkin_id']}/review", json={"decisions": decisions})
    assert r.status_code == 200, r.text
    return body["checkin_id"], r.json()


def _passport(client, jid, **params):
    r = client.get(f"/api/journals/{jid}/passport", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _card(pp, card_id):
    match = [c for c in pp["cards"] if c["card_id"] == card_id]
    assert len(match) == 1, [c["card_id"] for c in pp["cards"]]
    return match[0]


@pytest.fixture(scope="module")
def saved(client):
    """A journal with sleep + steps + pain confirmed and weight corrected to [lb_av] today."""
    jid = _journal(client)
    cid, _ = _save(client, jid, "slept 6 hours and walked 8000 steps")
    _save(client, jid, "pain 4 out of 10")
    _save(client, jid, "weighed 160", [{"proposal_id": "p-1", "action": "correct", "unit": "[lb_av]"}])
    return jid, cid, _passport(client, jid)


# --- shape: T6.1, T6.2 --------------------------------------------------------------------------


def test_passport_header_and_one_observation_card_per_concept(saved):
    jid, _, pp = saved
    HealthClonePassport.model_validate(pp)
    assert pp["display_name"] == "Health Clone Passport"
    assert pp["journal_id"] == jid and pp["member_id"] == "syn-001" and pp["mode"] == "demo"
    assert pp["ontology_version"] == "core-v1+u1" and pp["loinc_version"] == LOINC_VERSION
    obs = [c for c in pp["cards"] if c["kind"] == "observation"]
    assert [c["concept_id"] for c in obs] == [c.concept_id for c in load_registry().concepts()]
    patterns = [c for c in pp["cards"] if c["kind"] == "pattern"]
    assert {c["card_id"] for c in patterns} >= {"pattern:dp:adherence.protocol", "pattern:dp:symptom.severity"}


def test_t6_1_every_card_has_provenance_fields(saved):
    _, _, pp = saved
    for c in pp["cards"]:
        assert c["origin"] in ("observed", "simulated"), c["card_id"]
        assert c["source"] and c["method"] and len(c["limits"]) >= 1, c["card_id"]
        if c["status"] == "ready":
            assert isinstance(c["data_age_days"], int) and 0 <= c["data_age_days"] <= 14, c["card_id"]


def test_t6_2_every_thread_has_five_linked_steps_in_order(saved):
    _, _, pp = saved
    for c in pp["cards"]:
        steps = c["thread"]["steps"]
        assert [s["step"] for s in steps] == list(STEP_NAMES), c["card_id"]
        for s in steps:
            assert s["label"] and isinstance(s["link"], str) and s["link"], (c["card_id"], s)
            if s["label"] == "none":
                assert s["link"] == f"#passport/why-empty/{s['step']}", (c["card_id"], s)
                assert s["note"], (c["card_id"], s)


def test_thread_links_point_at_the_record_review_and_lab(saved):
    jid, cid, pp = saved
    sleep = _card(pp, "observation:chc:sleep-duration")
    source, observation, memory, explanation, evaluation = sleep["thread"]["steps"]
    assert source["link"] == f"#review/{cid}" and source["ref"] == cid
    rid = observation["record_id"]
    assert observation["link"] == f"/api/journals/{jid}/observations/{rid}"
    assert observation["event_id"] and observation["concept_id"] == "chc:sleep-duration"
    assert memory == {**memory, "ontology_version": "core-v1+u1", "readiness": "ready", "link": "#passport/inventory"}
    assert explanation["status"] == "shown" and explanation["evidence_ids"] == ["ev:nhlbi-how-much-sleep"]
    assert explanation["link"] == load_evidence().by_id("ev:nhlbi-how-much-sleep").url
    assert evaluation["membrane_verdict"] == "pass" and evaluation["rule_version"] == dsl.RULE_VERSION
    assert evaluation["run_id"] == RUN_ID and evaluation["link"] == f"#lab/{RUN_ID}"


def test_boundary_run_id_reads_the_committed_results():
    assert boundary_run_id() == RUN_ID


def test_boundary_run_id_is_none_without_results(tmp_path):
    assert boundary_run_id(tmp_path) is None


# --- suppression: T6.3 --------------------------------------------------------------------------


def test_t6_3_unsourced_concept_suppresses_explanation(saved):
    _, _, pp = saved
    assert not load_evidence().for_concept("chc:pain-severity")
    pain = _card(pp, "observation:chc:pain-severity")
    assert pain["status"] == "ready"
    assert pain["explanation"] is None and pain["explanation_status"] == "suppressed"
    assert pain["explanation_text"] == NOT_ENOUGH_EVIDENCE == "Not enough evidence"
    expl = pain["thread"]["steps"][3]
    assert expl["label"] == "none" and expl["link"] == "#passport/why-empty/explanation"


def test_sourced_ready_card_shows_explanation(saved):
    _, _, pp = saved
    sleep = _card(pp, "observation:chc:sleep-duration")
    assert sleep["explanation_status"] == "shown"
    assert sleep["explanation"] and sleep["explanation_text"] == sleep["explanation"]


def test_sourced_but_withheld_card_suppresses_explanation(saved):
    _, _, pp = saved
    hr = _card(pp, "observation:chc:heart-rate")
    assert load_evidence().for_concept("chc:heart-rate")
    assert hr["status"] == "withheld" and hr["explanation"] is None and hr["explanation_status"] == "suppressed"


# --- withheld: T6.4 -----------------------------------------------------------------------------


def test_t6_4_withheld_cards_carry_no_number(saved):
    _, _, pp = saved
    withheld = [c for c in pp["cards"] if c["status"] == "withheld"]
    assert withheld
    for c in withheld:
        assert c["value"] is None and c["unit"] is None and c["value_label"] is None, c["card_id"]
        assert c["data_age_days"] is None and c["reference_range"] is None, c["card_id"]
        assert c["message"] == WITHHELD_MESSAGE, c["card_id"]


# --- recorded value: T6.6 -----------------------------------------------------------------------


def test_t6_6_observation_value_is_the_recorded_value(client, saved):
    jid, _, pp = saved
    j = client.app.state.journals.get(jid)
    weight = _card(pp, "observation:chc:body-weight")
    rid = weight["thread"]["steps"][1]["record_id"]
    rec = j.provenance[rid]
    assert (weight["value"], weight["unit"]) == (rec.value, rec.unit) == (160.0, "[lb_av]")
    assert weight["origin"] == "observed" and weight["value_label"] == "You recorded"
    assert weight["data_age_days"] == 0
    for c in pp["cards"]:
        if c["kind"] == "observation":
            assert "interval" not in c and "score" not in c, c["card_id"]


def test_t6_6_latest_saved_value_wins(client):
    jid = _journal(client)
    _save(client, jid, "slept 6 hours")
    _save(client, jid, "slept 8 hours")
    assert _card(_passport(client, jid), "observation:chc:sleep-duration")["value"] == 8.0


def test_t6_6_value_older_than_14_days_is_withheld(client):
    jid = _journal(client)
    old = (TODAY - dt.timedelta(days=15)).isoformat()
    _save(client, jid, "slept 6 hours", [{"proposal_id": "p-1", "action": "correct", "date": old}])
    card = _card(_passport(client, jid), "observation:chc:sleep-duration")
    assert card["status"] == "withheld" and card["value"] is None and card["origin"] == "observed"
    edge = (TODAY - dt.timedelta(days=14)).isoformat()
    _save(client, jid, "slept 7 hours", [{"proposal_id": "p-1", "action": "correct", "date": edge}])
    card = _card(_passport(client, jid), "observation:chc:sleep-duration")
    assert (card["status"], card["value"], card["data_age_days"]) == ("ready", 7.0, 14)


def test_t6_6_pattern_card_rejected_by_is_ready_is_withheld(saved):
    _, _, pp = saved
    food = _card(pp, "pattern:dp:nutrition.food_log")
    assert food["status"] == "withheld" and food["value"] is None


def test_simulated_series_card_shows_the_latest_simulated_point(client, saved):
    jid, _, pp = saved
    j = client.app.state.journals.get(jid)
    as_of = journal_as_of(j)
    series = asyncio.run(j.memory.adapter.read_outcome_series("syn-001"))
    points = [p for r in series if r.metric_display == "Protocol adherence (logged)" for p in r.points]
    latest = max((p for p in points if p.observed_at <= as_of), key=lambda p: p.observed_at)
    card = _card(pp, "observation:chc:adherence-protocol")
    assert (card["status"], card["origin"], card["value_label"]) == ("ready", "simulated", "Simulated record")
    assert card["value"] == latest.value
    source = card["thread"]["steps"][0]
    assert source["link"] == "#research" and "seed" in source["ref"]


def test_pattern_card_is_the_existing_flag(saved):
    _, _, pp = saved
    adh = _card(pp, "pattern:dp:adherence.protocol")
    assert adh["status"] == "ready" and isinstance(adh["value"], float) and adh["unit"]


# --- SC9 / T4.3: nothing before review; a discard never shows ------------------------------------


def test_pending_and_discarded_values_never_reach_the_passport(client):
    jid = _journal(client)
    ck = client.post("/api/checkins", json={"journal_id": jid, "text": "slept 6 hours"}).json()
    assert _card(_passport(client, jid), "observation:chc:sleep-duration")["status"] == "withheld"
    r = client.post(f"/api/checkins/{ck['checkin_id']}/review",
                    json={"decisions": [{"proposal_id": "p-1", "action": "discard"}]})
    assert r.status_code == 200
    assert _card(_passport(client, jid), "observation:chc:sleep-duration")["status"] == "withheld"


def test_origin_is_observed_only_for_a_value_saved_in_this_journal(client):
    jid = _journal(client)
    pp = _passport(client, jid)
    assert [c["card_id"] for c in pp["cards"] if c["origin"] == "observed"] == []
    ck = client.post("/api/checkins", json={"journal_id": jid, "text": "slept 6 hours"}).json()
    assert [c["card_id"] for c in _passport(client, jid)["cards"] if c["origin"] == "observed"] == []
    client.post(f"/api/checkins/{ck['checkin_id']}/review",
                json={"decisions": [{"proposal_id": "p-1", "action": "confirm"}]})
    observed = [c["card_id"] for c in _passport(client, jid)["cards"] if c["origin"] == "observed"]
    assert observed == ["observation:chc:sleep-duration"]


# --- ranges (AM-1) ------------------------------------------------------------------------------


def test_sourced_range_sits_beside_a_ready_value(saved):
    _, _, pp = saved
    sleep = _card(pp, "observation:chc:sleep-duration")
    rr = sleep["reference_range"]
    src = load_evidence().by_id(rr["source_evidence_id"])
    assert (rr["low"], rr["high"], rr["unit"]) == (7.0, 9.0, "h")
    assert rr["population"] and rr["source_url"] == src.url
    assert sleep["reference_range_status"] == "shown"
    for forbidden in ("high", "low", "normal", "abnormal", "in_range", "flag", "interpretation"):
        assert forbidden not in {k for k in sleep if k not in ("reference_range",)}


def test_ready_unsourced_concept_has_no_range(saved):
    _, _, pp = saved
    pain = _card(pp, "observation:chc:pain-severity")
    assert pain["reference_range"] is None and pain["reference_range_status"] == "none"


def test_withheld_sourced_concept_withholds_its_range(saved):
    _, _, pp = saved
    hr = _card(pp, "observation:chc:heart-rate")
    assert hr["reference_range"] is None and hr["reference_range_status"] == "withheld"


# --- T6.5: safe strings, no plausible bounds, every range number traces -------------------------

_NUMBER_TOKEN = re.compile(r"(?<![\w.\-])-?\d+(?:\.\d+)?(?![\w.\-])")
_BOUNDS = {t for c in load_registry().concepts() for b in c.plausible for t in (f"{b:g}", repr(float(b)))}
# The member's recorded value and the day count are not leak channels; range numbers are checked
# against their source below.
_EXEMPT = frozenset({"value", "data_age_days", "reference_range"})
# UCUM "1" (dimensionless, adherence) is a unit, not a number.
_UNITS = frozenset(u for c in load_registry().concepts() for u in (c.unit, *c.alt_units))
# A concept's name may hold digits ("Steps in 24 hours", "PHQ-2"): a name, not a bound.
_NAMES = frozenset(
    [c.display for c in load_registry().concepts()]
    + [n.label or n.display for n in slice_ontology().nodes.values()]
)


def _strings(obj, key=None):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(v, k)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v, key)
    elif isinstance(obj, str):
        yield key, obj


def _no_bounds(obj, key=None):
    if key in _EXEMPT or (key in ("title", "display") and obj in _NAMES) or (key == "unit" and obj in _UNITS):
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            _no_bounds(v, k)
    elif isinstance(obj, list):
        for v in obj:
            _no_bounds(v, key)
    elif isinstance(obj, bool) or obj is None:
        return
    elif isinstance(obj, (int, float)):
        assert f"{obj:g}" not in _BOUNDS, (key, obj)
    else:
        assert not set(_NUMBER_TOKEN.findall(str(obj))) & _BOUNDS, (key, obj)


def test_t6_5_every_string_is_narration_and_membrane_safe(saved):
    _, _, pp = saved
    for key, text in _strings(pp):
        if key in ("link", "source_url", "ref", "record_id", "event_id", "run_id") or text.startswith("#"):
            continue
        assert_narration_safe(text)
        v = dsl.check(text)
        assert v.passed, (key, text, v.violations)


def test_t6_5_no_plausible_bound_and_every_range_number_traces(saved, client):
    _, _, pp = saved
    _no_bounds(pp)
    _no_bounds(client.get("/api/inventory").json())
    ev = load_evidence()
    ranged = [c for c in pp["cards"] if c["reference_range"] is not None]
    assert ranged
    for c in ranged:
        rr = c["reference_range"]
        src = ev.by_id(rr["source_evidence_id"])
        assert src is not None, c["card_id"]
        stated = [r for r in src.stated_ranges if r.concept_id == c["concept_id"]]
        assert stated and (stated[0].low, stated[0].high) == (rr["low"], rr["high"]), c["card_id"]


# --- T5.4 inventory -----------------------------------------------------------------------------


def test_t5_4_inventory_lists_verticals_and_gaps(client, saved):
    _, _, pp = saved
    inv = client.get("/api/inventory").json()
    assert set(inv["gaps"]) >= {"labs", "conditions", "medications", "care history", "preventive care"}
    assert inv["loinc_version"] == LOINC_VERSION and inv["reviewer_status"] == REVIEWER_STATUS
    assert [v["vertical"] for v in inv["verticals"]] == ["vitals_body", "behaviour_function", "symptoms_wellbeing"]
    for v in inv["verticals"]:
        assert v["label"] and len(v["concepts"]) >= 4
    # /api/inventory keeps the registry gap ids (T5.4); the passport shows each as a guard-safe label (T6.5).
    assert pp["inventory"] == {"verticals": inv["verticals"], "gaps": inv["gap_labels"]}
    assert len(inv["gap_labels"]) == len(inv["gaps"]) and "Screenings and check-ups" in inv["gap_labels"]
    for label in inv["gap_labels"]:
        assert_narration_safe(label)


# --- HTTP ---------------------------------------------------------------------------------------


def test_passport_unknown_journal_is_404(client):
    r = client.get(f"/api/journals/{'f' * 32}/passport")
    assert r.status_code == 404 and r.json() == {"error": "unknown_journal"}


def test_passport_day_moves_as_of(client):
    jid = _journal(client)
    _save(client, jid, "slept 6 hours")
    pp = _passport(client, jid, day=27)
    assert pp["as_of"].startswith((TODAY - dt.timedelta(days=1)).isoformat())
    assert _card(pp, "observation:chc:sleep-duration")["status"] == "withheld"
    for bad in (29, -1, "x", "1.5", 10**30, "²", ""):
        r = client.get(f"/api/journals/{jid}/passport", params={"day": bad})
        assert (r.status_code, r.json()) == (422, {"error": "invalid_day", "max_day": 28}), bad
    assert _passport(client, jid, day=28) == _passport(client, jid)
    assert _passport(client, jid, day=0)["as_of"] == f"{START_DATE.date().isoformat()}T12:00:00Z"


def test_view_function_matches_the_route(client, saved):
    jid, _, pp = saved
    j = client.app.state.journals.get(jid)
    direct = asyncio.run(health_clone_passport(j, journal_as_of(j)))
    assert direct.model_dump(mode="json") == pp


# --- QG P2.2: suppression on a failed safety check, missing lab run, fixture source -------------


class _EvidenceWith:
    """The real evidence registry, with one concept's sources replaced."""

    def __init__(self, concept_id, sources):
        self._real, self._cid, self._sources = load_evidence(), concept_id, tuple(sources)

    def for_concept(self, code):
        return self._sources if code == self._cid else self._real.for_concept(code)

    def by_id(self, evidence_id):
        return self._real.by_id(evidence_id)


def test_explanation_failing_the_membrane_is_suppressed(client, monkeypatch):
    from daypart.passport import view

    real = load_evidence().by_id("ev:nhlbi-how-much-sleep")
    dosing = real.model_copy(update={"supports": "Take 500 mg of melatonin every night before bed."})
    monkeypatch.setattr(view, "load_evidence", lambda: _EvidenceWith("chc:sleep-duration", [dosing]))
    jid = _journal(client)
    _save(client, jid, "slept 6 hours")
    card = _card(_passport(client, jid), "observation:chc:sleep-duration")
    assert card["status"] == "ready"
    assert card["explanation"] is None and card["explanation_status"] == "suppressed"
    assert card["explanation_text"] == NOT_ENOUGH_EVIDENCE
    _, _, _, expl, evaluation = card["thread"]["steps"]
    assert expl["status"] == "suppressed" and expl["template_id"] == "why-tracked-v1"
    assert expl["evidence_ids"] == [real.evidence_id] and expl["note"].startswith("the explanation failed")
    assert evaluation["membrane_verdict"] == "blocked" and evaluation["label"] == "Membrane check: blocked"
    assert "500 mg" not in str(card)


def test_explanation_rewritten_by_safe_text_is_suppressed(client, monkeypatch):
    from daypart.passport import view

    monkeypatch.setattr(view, "safe_text", lambda text, *a, **k: "[withheld]" if text.startswith("Why") else text)
    jid = _journal(client)
    _save(client, jid, "slept 6 hours")
    card = _card(_passport(client, jid), "observation:chc:sleep-duration")
    assert card["explanation"] is None and card["explanation_status"] == "suppressed"
    assert card["thread"]["steps"][4]["membrane_verdict"] == "pass"


def test_evaluation_step_without_a_lab_run(client, monkeypatch):
    from daypart.passport import view

    monkeypatch.setattr(view, "boundary_run_id", lambda *a, **k: None)
    jid = _journal(client)
    _save(client, jid, "slept 6 hours")
    pp = _passport(client, jid)
    evaluation = _card(pp, "observation:chc:sleep-duration")["thread"]["steps"][4]
    assert evaluation["run_id"] is None and evaluation["label"] == "Membrane check: pass"
    assert evaluation["link"] == "#passport/why-empty/evaluation" and evaluation["note"]
    assert not [s for c in pp["cards"] for s in c["thread"]["steps"] if s["link"].startswith("#lab/")]


def test_fixture_sourced_card_links_its_fixture(client):
    jid = _journal(client)
    ck = client.post("/api/checkins", json={"journal_id": jid, "fixture_id": "demo-bp-cuff"}).json()
    decisions = [{"proposal_id": p["proposal_id"], "action": "discard" if p["flags"] else "confirm"}
                 for p in ck["proposals"]]
    confirmed = {p["concept_code"] for p in ck["proposals"] if not p["flags"]}
    assert confirmed, ck["proposals"]
    r = client.post(f"/api/checkins/{ck['checkin_id']}/review", json={"decisions": decisions})
    assert r.status_code == 200, r.text
    pp = _passport(client, jid)
    reg = load_registry()
    for code in confirmed:
        card = _card(pp, f"observation:{reg.by_code(code).concept_id}")
        source = card["thread"]["steps"][0]
        assert (card["origin"], card["method"], card["value_label"]) == ("observed", "fixture-sidecar-v1", "You recorded")
        assert source["ref"] == "demo-bp-cuff" and source["link"] == "/api/fixtures/demo-bp-cuff"
        assert source["label"] == "Imported photo"  # AM-2 D2 (QG P6.1 C6): was "Demo fixture image"
        assert client.get(source["link"]).status_code == 200


def test_pattern_source_text_follows_its_thread(saved):
    _, _, pp = saved
    for c in (c for c in pp["cards"] if c["kind"] == "pattern"):
        source_step = c["thread"]["steps"][0]
        if source_step["label"] == "none":
            assert c["source"] == "No record yet", c["card_id"]
            assert not any("simulated cohort" in limit for limit in c["limits"]), c["card_id"]
        else:
            assert c["source"].startswith("Pattern score from simulated cohort data"), c["card_id"]


def test_pattern_card_links_the_latest_save_on_a_same_time_tie(client):
    # QG P2.3 C2: saves on one day share 12:00 UTC; the later save (higher event index) is linked.
    jid = _journal(client)
    _save(client, jid, "adherence 0%")  # -e1
    _save(client, jid, "adherence 100%")  # -e2
    adh = _card(_passport(client, jid), "pattern:dp:adherence.protocol")
    obs = adh["thread"]["steps"][1]
    assert obs["event_id"].endswith("-e2")


# --- P2 phase gate --------------------------------------------------------------------------------


def test_c1_deeply_nested_results_give_no_run_id(tmp_path):
    """C1: a pathologically nested artefact is "no run id", never a passport 500 (as lab._read)."""
    (tmp_path / "pipeline.json").write_text("[" * 200_000 + "]" * 200_000, "utf-8")
    (tmp_path / "boundary_eval.json").write_text("[" * 200_000 + "]" * 200_000, "utf-8")
    assert boundary_run_id(tmp_path) is None


def test_t1_day_back_in_time_ignores_later_saves(client):
    """T1: ?day=N shows the value valid at day N; a value saved for a later day never leaks back."""
    jid = _journal(client)
    day20 = (START_DATE + dt.timedelta(days=20)).date().isoformat()
    c1, _ = _save(client, jid, "slept 6 hours", [{"proposal_id": "p-1", "action": "correct", "date": day20}])
    _save(client, jid, "slept 8 hours")
    past = _card(_passport(client, jid, day=25), "observation:chc:sleep-duration")
    assert (past["status"], past["value"], past["data_age_days"]) == ("ready", 6.0, 5)
    assert c1 in past["thread"]["steps"][0]["ref"]
    now = _card(_passport(client, jid, day=28), "observation:chc:sleep-duration")
    assert (now["status"], now["value"]) == ("ready", 8.0)
    before = _card(_passport(client, jid, day=19), "observation:chc:sleep-duration")
    assert before["origin"] != "observed"


# --- QG-plan K3: a save_unmapped value with a concept still never shows on the passport (SC9) -----


def test_save_unmapped_blocking_value_with_a_concept_stays_off_the_passport(client):
    jid = _journal(client)
    before = _card(_passport(client, jid), "observation:chc:body-weight")
    _ck, saved_body = _save(client, jid, "weighed 160", decisions=[{"proposal_id": "p-1", "action": "save_unmapped"}])
    (rid,) = saved_body["records"]
    rec = client.get(f"/api/journals/{jid}/observations/{rid}")
    assert rec.status_code == 200, rec.text
    rec = rec.json()
    # The precondition the mutant needs: the record keeps its concept but is not mapped.
    assert rec["status"] == "unmapped" and rec["concept_id"] == "chc:body-weight"
    card = _card(_passport(client, jid), "observation:chc:body-weight")
    assert card["status"] == before["status"] == "withheld"
    assert card["origin"] == "simulated" and card["value"] is None
    assert rid not in repr(card["thread"])

"""HAC-38 P2 task 8: the suggested next step (A&D §4.7, R7).

Covers T7.1-T7.4: after a saved check-in the journal gets one deterministic step (rules in §4.7
order, no thresholds on clinical values), the step passes the membrane or is replaced by the
clinician-handoff text, "choose" writes one ``act:goal_set`` ActionEvent and the other choices
write nothing, and there is no step before any saved check-in. Synthetic only.
"""

import asyncio
import datetime as dt

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from daypart.checkin import next_step
from daypart.checkin.next_step import (
    ASK_PROFESSIONAL_LABEL,
    HANDOFF_TEXT,
    OPTIONS,
    AdherenceDay,
    select_intent,
)
from daypart.demo.app import create_app
from daypart.eval import POLICY_TEXT
from daypart.membrane import dsl
from daypart.memory.events import ActionEvent
from syntropy.lhm.metrics.claims import assert_narration_safe

DOSING = "Take 500 mg of ibuprofen twice a day."
D0 = dt.date(2026, 1, 1)


@pytest.fixture()
def client():
    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("DAYPART_REAL_INPUT", raising=False)
        with TestClient(create_app(cohort_seed=0)) as c:
            yield c


def _journal(client, member_id="syn-001"):
    r = client.post("/api/journals", json={"member_id": member_id})
    assert r.status_code == 201, r.text
    return r.json()["journal_id"]


def _save(client, jid, text):
    ck = client.post("/api/checkins", json={"journal_id": jid, "text": text})
    assert ck.status_code == 201, ck.text
    body = ck.json()
    decisions = [{"proposal_id": p["proposal_id"], "action": "confirm"} for p in body["proposals"]]
    r = client.post(f"/api/checkins/{body['checkin_id']}/review", json={"decisions": decisions})
    assert r.status_code == 200, r.text
    return body["checkin_id"]


def _actions(client, jid):
    j = client.app.state.journals.get(jid)
    return [e for e in j.all_events() if isinstance(e, ActionEvent)]


def _days(*values):
    """Adherence days ending today: ``_days(1, 0, 0)`` = two days ago adhered, then two misses."""
    n = len(values)
    return tuple(AdherenceDay(date=D0 - dt.timedelta(days=n - 1 - i), value=v) for i, v in enumerate(values))


# --- T7.1: the step after a saved check-in --------------------------------------------------------


def test_t7_1_step_after_saved_checkin(client):
    jid = _journal(client)
    cid = _save(client, jid, "slept 6 hours and walked 8000 steps")
    r = client.get(f"/api/journals/{jid}/next-step")
    assert r.status_code == 200, r.text
    step = r.json()
    assert set(step) >= {"step_id", "text", "reason", "intent", "membrane", "options", "replaced"}
    assert step["options"] == ["choose", "defer", "ask_professional"] == list(OPTIONS)
    assert step["text"].strip() and step["reason"].strip()
    assert step["intent"] in {"barrier_problem_solving", "celebrate_streak", "check_in_question"}
    assert step["text"] == POLICY_TEXT[step["intent"]]
    assert step["replaced"] is False
    assert step["membrane"] == {"decision": "pass", "rule_hits": []}
    assert cid in step["step_id"]
    for s in (step["text"], step["reason"]):
        assert_narration_safe(s)
        assert dsl.check(s).passed


def test_t7_1_step_is_deterministic(client):
    jid = _journal(client)
    _save(client, jid, "walked 8000 steps")
    a = client.get(f"/api/journals/{jid}/next-step").json()
    b = client.get(f"/api/journals/{jid}/next-step").json()
    assert a == b


def test_symptom_report_routes_to_a_person_and_names_the_concept_not_the_value(client):
    jid = _journal(client)
    _save(client, jid, "pain 4/10")
    step = client.get(f"/api/journals/{jid}/next-step").json()
    assert step["intent"] == "clinician_handoff"
    assert step["text"] == HANDOFF_TEXT
    assert step["replaced"] is False
    assert "pain" in step["reason"].lower()
    assert "4" not in step["reason"]


def test_only_the_last_saved_checkin_counts(client):
    jid = _journal(client)
    _save(client, jid, "pain 4/10")
    _save(client, jid, "walked 8000 steps")
    # A pending (unreviewed) symptom check-in does not count either.
    assert client.post("/api/checkins", json={"journal_id": jid, "text": "pain 6/10"}).status_code == 201
    step = client.get(f"/api/journals/{jid}/next-step").json()
    assert step["intent"] != "clinician_handoff"


# --- §4.7 rule order (pure selection) -----------------------------------------------------------


@pytest.mark.parametrize(
    ("symptom", "days", "intent"),
    [
        ("Pain severity", _days(1, 1, 1, 1), "clinician_handoff"),  # rule 1 beats a streak
        ("Pain severity", _days(1, 0, 0), "clinician_handoff"),  # rule 1 beats missed adherence
        (None, _days(1, 0, 0), "barrier_problem_solving"),
        (None, _days(0, 1, 0), "barrier_problem_solving"),
        (None, _days(0, 0, 0), "barrier_problem_solving"),
        (None, _days(1, 1, 1), "celebrate_streak"),
        (None, _days(0, 1, 1, 1), "celebrate_streak"),
        (None, _days(1, 1), "check_in_question"),  # streak of 2
        (None, _days(1, 0, 1, 1), "check_in_question"),  # one miss of 3, streak of 2
        (None, _days(1, 1, 0), "check_in_question"),  # one miss, streak broken
        (None, (), "check_in_question"),
    ],
)
def test_rules_apply_in_order(symptom, days, intent):
    assert select_intent(symptom, days, today=D0).intent == intent


def test_days_outside_the_last_three_do_not_count_as_misses():
    assert select_intent(None, _days(0, 0, 1, 1), today=D0).intent == "check_in_question"


def test_a_gap_day_breaks_the_streak():
    days = (AdherenceDay(D0 - dt.timedelta(days=3), 1.0), AdherenceDay(D0 - dt.timedelta(days=1), 1.0),
            AdherenceDay(D0, 1.0))
    assert select_intent(None, days, today=D0).intent == "check_in_question"


def test_a_saved_adherence_value_overrides_the_simulated_day(client):
    jid = _journal(client)
    j = client.app.state.journals.get(jid)
    _save(client, jid, "adherence 0%")
    days = asyncio.run(next_step.adherence_days(j))
    assert days[-1].date == j.today and days[-1].value == 0.0


# --- T7.2: a step the membrane blocks is replaced ------------------------------------------------


def test_t7_2_dosing_text_is_replaced_by_the_handoff(client, monkeypatch):
    monkeypatch.setattr(next_step, "POLICY_TEXT", {k: DOSING for k in POLICY_TEXT})
    jid = _journal(client)
    _save(client, jid, "walked 8000 steps")
    step = client.get(f"/api/journals/{jid}/next-step").json()
    assert step["replaced"] is True
    assert step["text"] == POLICY_TEXT["clinician_handoff"] == HANDOFF_TEXT
    assert step["intent"] == "clinician_handoff"
    assert step["label"] == ASK_PROFESSIONAL_LABEL == "Ask a professional"
    assert step["membrane"]["decision"] == "escalate"
    assert DOSING not in repr(step)


def test_t7_2_also_holds_when_the_eval_library_is_patched(client, monkeypatch):
    from daypart.eval import policies

    monkeypatch.setattr(policies, "POLICY_TEXT", {k: DOSING for k in POLICY_TEXT})
    jid = _journal(client)
    _save(client, jid, "walked 8000 steps")
    step = client.get(f"/api/journals/{jid}/next-step").json()
    assert step["replaced"] is True and step["text"] == HANDOFF_TEXT


def test_dsl_hits_are_reported_when_layer0_passes(client, monkeypatch):
    patched = dict(POLICY_TEXT)
    for k in patched:
        patched[k] = "You should increase your dose tomorrow."
    monkeypatch.setattr(next_step, "POLICY_TEXT", patched)
    jid = _journal(client)
    _save(client, jid, "walked 8000 steps")
    step = client.get(f"/api/journals/{jid}/next-step").json()
    assert step["replaced"] is True
    assert step["membrane"]["decision"] == "escalate"


# --- T7.3: choices -------------------------------------------------------------------------------


def test_t7_3_choose_writes_one_goal_set(client):
    jid = _journal(client)
    _save(client, jid, "walked 8000 steps")
    step = client.get(f"/api/journals/{jid}/next-step").json()
    r = client.post(f"/api/journals/{jid}/next-step", json={"step_id": step["step_id"], "choice": "choose"})
    assert r.status_code == 200, r.text
    eid = r.json()["recorded"]
    acts = _actions(client, jid)
    assert [(a.event_id, a.code) for a in acts] == [(eid, "act:goal_set")]
    j = client.app.state.journals.get(jid)
    assert acts[0].member_id == j.member.member_id
    assert acts[0].occurred_at == dt.datetime.combine(j.today, dt.time(12), dt.timezone.utc)
    # Choosing the same step again records nothing new.
    r2 = client.post(f"/api/journals/{jid}/next-step", json={"step_id": step["step_id"], "choice": "choose"})
    assert r2.status_code == 200 and r2.json()["recorded"] == eid
    assert len(_actions(client, jid)) == 1


@pytest.mark.parametrize("choice", ["defer", "ask_professional"])
def test_t7_3_other_choices_write_nothing(client, choice):
    jid = _journal(client)
    _save(client, jid, "walked 8000 steps")
    before = len(client.app.state.journals.get(jid).all_events())
    step = client.get(f"/api/journals/{jid}/next-step").json()
    r = client.post(f"/api/journals/{jid}/next-step", json={"step_id": step["step_id"], "choice": choice})
    assert r.status_code == 200, r.text
    assert r.json() == {"recorded": None}
    assert len(client.app.state.journals.get(jid).all_events()) == before


def test_a_new_saved_checkin_gives_a_new_step_id(client):
    jid = _journal(client)
    _save(client, jid, "walked 8000 steps")
    old = client.get(f"/api/journals/{jid}/next-step").json()["step_id"]
    _save(client, jid, "slept 7 hours")
    new = client.get(f"/api/journals/{jid}/next-step").json()["step_id"]
    assert new != old
    r = client.post(f"/api/journals/{jid}/next-step", json={"step_id": old, "choice": "choose"})
    assert r.status_code == 422 and r.json() == {"error": "unknown_step"}
    assert _actions(client, jid) == []


# --- T7.4 and refusals ---------------------------------------------------------------------------


def test_t7_4_no_step_before_a_saved_checkin(client):
    jid = _journal(client)
    r = client.get(f"/api/journals/{jid}/next-step")
    assert r.status_code == 409 and r.json() == {"error": "no_saved_checkin"}
    # A pending check-in is not a saved one.
    assert client.post("/api/checkins", json={"journal_id": jid, "text": "walked 8000 steps"}).status_code == 201
    r = client.get(f"/api/journals/{jid}/next-step")
    assert r.status_code == 409 and r.json() == {"error": "no_saved_checkin"}


def test_choice_before_a_saved_checkin_is_refused(client):
    jid = _journal(client)
    r = client.post(f"/api/journals/{jid}/next-step", json={"step_id": "x", "choice": "choose"})
    assert r.status_code == 422 and r.json() == {"error": "unknown_step"}
    assert _actions(client, jid) == []


def test_unknown_journal_is_404(client):
    assert client.get("/api/journals/nope/next-step").status_code == 404
    r = client.post("/api/journals/nope/next-step", json={"step_id": "x", "choice": "defer"})
    assert r.status_code == 404 and r.json() == {"error": "unknown_journal"}


@pytest.mark.parametrize(
    "body",
    [
        {"step_id": "x", "choice": "maybe"},
        {"step_id": "x"},
        {"choice": "choose"},
        {"step_id": 3, "choice": "choose"},
        {"step_id": "x", "choice": "choose", "extra": 1},
        [],
    ],
)
def test_malformed_choice_is_422(client, body):
    jid = _journal(client)
    _save(client, jid, "walked 8000 steps")
    r = client.post(f"/api/journals/{jid}/next-step", json=body)
    assert r.status_code == 422 and r.json() == {"error": "invalid_request"}
    assert _actions(client, jid) == []


def test_non_json_choice_is_422(client):
    jid = _journal(client)
    _save(client, jid, "walked 8000 steps")
    r = client.post(f"/api/journals/{jid}/next-step", content=b"not json", headers={"content-type": "application/json"})
    assert r.status_code == 422 and r.json() == {"error": "invalid_request"}


@pytest.mark.parametrize(
    ("symptom", "days"),
    [("Pain severity", ()), (None, _days(0, 0, 0)), (None, _days(1, 1, 1)), (None, ())],
)
def test_every_rule_text_and_reason_is_safe(symptom, days):
    sel = select_intent(symptom, days, today=D0)
    for s in (POLICY_TEXT[sel.intent], sel.reason):
        assert s.strip()
        assert_narration_safe(s)
        assert dsl.check(s).passed


# --- QG P2.3 regressions ---------------------------------------------------------------------------


def _create(client, jid, text):
    ck = client.post("/api/checkins", json={"journal_id": jid, "text": text})
    assert ck.status_code == 201, ck.text
    return ck.json()


def _review(client, body, action="confirm"):
    decisions = [{"proposal_id": p["proposal_id"], "action": action} for p in body["proposals"]]
    r = client.post(f"/api/checkins/{body['checkin_id']}/review", json={"decisions": decisions})
    assert r.status_code == 200, r.text


def test_c1_last_saved_is_by_save_order_not_creation_order(client):
    jid = _journal(client)
    a = _create(client, jid, "pain 4/10")
    b = _create(client, jid, "walked 8000 steps")
    _review(client, b)
    _review(client, a)  # A is created first but saved last
    step = client.get(f"/api/journals/{jid}/next-step").json()
    assert step["step_id"] == f"ns-{a['checkin_id']}"
    assert step["intent"] == "clinician_handoff"
    r = client.post(f"/api/journals/{jid}/next-step", json={"step_id": step["step_id"], "choice": "choose"})
    assert r.status_code == 200 and r.json()["recorded"]

"""HAC-38 P6.1 (AM-2 D3, addendum G33): the continuous-adaptation timeline.

``GET /api/journals/{id}/timeline`` is read-only. Per saved check-in, in save order, it lists the
EventLog appends, how the passport changed (cards that became ready, value changes, simulated ->
observed) and how the suggested next step changed. Synthetic only.
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from daypart.demo.app import create_app  # noqa: E402

CHANGES = {"became_ready", "withheld", "value_changed", "now_observed"}


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


def _checkin(client, jid, text):
    ck = client.post("/api/checkins", json={"journal_id": jid, "text": text})
    assert ck.status_code == 201, ck.text
    return ck.json()


def _save(client, jid, text, action="confirm"):
    body = _checkin(client, jid, text)
    decisions = [{"proposal_id": p["proposal_id"], "action": action} for p in body["proposals"]]
    r = client.post(f"/api/checkins/{body['checkin_id']}/review", json={"decisions": decisions})
    assert r.status_code == 200, r.text
    return body["checkin_id"], r.json()


def test_unknown_journal_is_404(client):
    r = client.get("/api/journals/nope/timeline")
    assert r.status_code == 404 and r.json() == {"error": "unknown_journal"}


def test_empty_before_any_save(client):
    jid = _journal(client)
    _checkin(client, jid, "slept 6 hours")  # pending, never reviewed: not on the timeline
    r = client.get(f"/api/journals/{jid}/timeline")
    assert r.status_code == 200
    body = r.json()
    assert body["journal_id"] == jid and body["member_id"] == "syn-001"
    assert body["version"] == "timeline-v1"
    assert body["entries"] == []


def test_one_entry_per_saved_checkin_in_save_order_with_its_appends(client):
    jid = _journal(client)
    c1, out1 = _save(client, jid, "slept 6 hours and walked 8000 steps")
    c2, out2 = _save(client, jid, "pulse 64 bpm")
    entries = client.get(f"/api/journals/{jid}/timeline").json()["entries"]
    assert [e["checkin_id"] for e in entries] == [c1, c2]
    assert [e["index"] for e in entries] == [1, 2]
    first = entries[0]
    assert [a["event_id"] for a in first["appends"]] == out1["written"]
    assert [a["record_id"] for a in first["appends"]] == out1["records"]
    by_code = {a["code"]: a for a in first["appends"]}
    assert by_code["93832-4"]["value"] == 6 and by_code["93832-4"]["unit"] == "h"
    assert by_code["55423-8"]["value"] == 8000
    assert [a["event_id"] for a in entries[1]["appends"]] == out2["written"]


def test_appends_carry_the_value_as_recorded(client):
    jid = _journal(client)
    _save(client, jid, "weight 160 lb")
    (entry,) = client.get(f"/api/journals/{jid}/timeline").json()["entries"]
    (a,) = entry["appends"]
    assert (a["value"], a["unit"]) == (160, "[lb_av]")  # never the canonical kg value


def test_passport_delta_names_the_cards_the_save_changed(client):
    jid = _journal(client)
    _save(client, jid, "slept 6 hours")
    (entry,) = client.get(f"/api/journals/{jid}/timeline").json()["entries"]
    changes = {c["card_id"]: c for c in entry["passport_changes"]}
    sleep = changes["observation:" + _concept_id(client, "93832-4")]
    assert sleep["change"] in {"became_ready", "now_observed"}
    assert sleep["after"] == {"status": "ready", "origin": "observed", "value": 6.0, "unit": "h"}
    assert all(c["change"] in CHANGES for c in entry["passport_changes"])
    # only cards that changed are listed: the pulse card was not touched by a sleep save
    assert "observation:" + _concept_id(client, "8867-4") not in changes


def test_second_save_of_the_same_concept_is_a_value_change(client):
    jid = _journal(client)
    _save(client, jid, "slept 6 hours")
    _save(client, jid, "slept 8 hours")
    entries = client.get(f"/api/journals/{jid}/timeline").json()["entries"]
    cid = "observation:" + _concept_id(client, "93832-4")
    change = {c["card_id"]: c for c in entries[1]["passport_changes"]}[cid]
    assert change["change"] == "value_changed"
    assert change["before"]["value"] == 6.0 and change["after"]["value"] == 8.0


def test_next_step_change_per_entry(client):
    jid = _journal(client)
    _save(client, jid, "slept 6 hours")
    _save(client, jid, "pain 4 out of 10")
    entries = client.get(f"/api/journals/{jid}/timeline").json()["entries"]
    first, second = entries[0]["next_step"], entries[1]["next_step"]
    assert first["before"] is None and first["changed"] is True
    assert first["after"]["step_id"] == f"ns-{entries[0]['checkin_id']}"
    assert second["before"] == first["after"]
    assert second["after"]["intent"] == "clinician_handoff"  # a pain report goes to a person
    assert second["changed"] is True
    # the last entry's step is the journal's live step
    live = client.get(f"/api/journals/{jid}/next-step").json()
    assert second["after"]["step_id"] == live["step_id"] and second["after"]["text"] == live["text"]


def test_a_fully_discarded_save_is_listed_with_no_appends(client):
    jid = _journal(client)
    cid, out = _save(client, jid, "slept 6 hours", action="discard")
    (entry,) = client.get(f"/api/journals/{jid}/timeline").json()["entries"]
    assert entry["checkin_id"] == cid and entry["appends"] == [] and entry["passport_changes"] == []


def test_timeline_is_read_only(client):
    jid = _journal(client)
    _save(client, jid, "slept 6 hours and walked 8000 steps")
    j = client.app.state.journals.get(jid)
    before = (len(j.events), dict(j.provenance), list(j.checkins), j.last_saved_checkin_id, j.event_count)
    a = client.get(f"/api/journals/{jid}/timeline").json()
    b = client.get(f"/api/journals/{jid}/timeline").json()
    assert a == b
    after = (len(j.events), dict(j.provenance), list(j.checkins), j.last_saved_checkin_id, j.event_count)
    assert before == after


def test_goal_choice_does_not_disturb_the_timeline(client):
    jid = _journal(client)
    _save(client, jid, "slept 6 hours")
    before = client.get(f"/api/journals/{jid}/timeline").json()
    step = client.get(f"/api/journals/{jid}/next-step").json()
    assert client.post(f"/api/journals/{jid}/next-step", json={"step_id": step["step_id"], "choice": "choose"}).status_code == 200
    assert client.get(f"/api/journals/{jid}/timeline").json() == before


def test_no_plausible_bound_in_the_response(client):
    jid = _journal(client)
    _save(client, jid, "slept 6 hours and walked 8000 steps")
    text = client.get(f"/api/journals/{jid}/timeline").text
    assert "plausible" not in text and "100000" not in text


def _concept_id(client, code):
    from daypart.memory.registry import load_registry

    c = load_registry().by_code(code)
    assert c is not None
    return c.concept_id

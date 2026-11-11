"""Sealed challenge suite — H3 passport inclinations (HAC-75, HAC-78).

Written double-blind from docs/daypart/contracts/CONTRACT-slice-E-addendum-HAC-75-rm.md H3, with
the endpoint shapes of workstreams/daypart/AND.md (``POST /api/journals``,
``GET /api/journals/{id}/passport``, ``HealthClonePassport`` in ``passport/view.py``,
``create_app`` in ``daypart/demo/app.py``). The implementation was never read.

Categories:
  functional/passport-incl-model   HealthClonePassport.inclinations field; research Passport unchanged
  integration/passport-incl-api    GET passport for a syn- journal and the persona-v1 journal
  integration/passport-incl-fail   building the inclinations raises -> null, rest of passport unchanged

Ambiguities resolved:
  * Fail-closed is forced black-box: every loaded ``daypart.*`` module attribute that *is* one of
    ``daypart.rm.inclinations.inclinations``, ``daypart.rm.model.trained`` or
    ``daypart.rm.jev.answers_for`` / ``simulate_answers`` is replaced by a function that raises, so
    the test does not depend on how the view imports them. Caches of ``trained`` are not touched; the
    raise in ``inclinations`` is enough to make "building it" raise.
  * "Rest of the passport unchanged" compares the JSON with ``inclinations`` removed, for the same
    journal and the same explicit ``?day=``.
  * Forbidden words are matched case-insensitively at a word start (plurals count).
"""

from __future__ import annotations

import re
import sys

import pytest

FORBIDDEN = re.compile(r"\b(logit|reward|grpo|feature|intent|model|weight|policy|latent)", re.IGNORECASE)


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from daypart.demo.app import create_app

    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("DAYPART_REAL_INPUT", raising=False)
        app = create_app()
    with TestClient(app) as c:
        yield c


def _journal(client, body) -> str:
    r = client.post("/api/journals", json=body)
    assert r.status_code == 201, r.text
    return r.json()["journal_id"]


@pytest.fixture(scope="module")
def syn_journal(client):
    return _journal(client, {"member_id": "syn-001"})


@pytest.fixture(scope="module")
def persona_journal(client):
    return _journal(client, {"persona": "persona-v1"})


def _passport(client, jid, day=None):
    url = f"/api/journals/{jid}/passport" + ("" if day is None else f"?day={day}")
    r = client.get(url)
    assert r.status_code == 200, r.text
    return r.json()


def _member_strings(inc: dict) -> list[str]:
    out = [d["label"] for d in inc["drivers"]]
    for i in inc["insights"]:
        out += [i["title"], i["action"], i["reason"]]
    out.append(inc["note"])
    return out


def _check_inc_json(inc):
    from syntropy.lhm.metrics.claims import assert_narration_safe

    from daypart.membrane.dsl import check

    assert isinstance(inc, dict), "inclinations must be present for this journal"
    assert inc["title"] == "Inclinations"
    assert inc["data"] == "synthetic"
    assert inc["jev_version"] == "jev-v1"
    assert inc["drivers"], "drivers must be shown"
    assert 1 <= len(inc["insights"]) <= 3
    shown = {d["driver_id"] for d in inc["drivers"]}
    for i in inc["insights"]:
        assert i["driver"] in shown, "each insight links to a shown driver"
        assert i["reason"].startswith("Why: ")
        assert i["estimated_lift_points"] > 0
    shares = [d["share"] for d in inc["drivers"]]
    assert abs(sum(shares) - 1.0) <= 0.01
    assert shares == sorted(shares, reverse=True)
    for s in _member_strings(inc):
        assert isinstance(s, str) and s.strip()
        assert not FORBIDDEN.search(s), s
        assert_narration_safe(s)
        assert check(s).passed, s


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #


@pytest.mark.category("functional/passport-incl-model")
class TestModels:
    def test_health_clone_passport_field(self):
        from daypart.passport.view import HealthClonePassport

        f = HealthClonePassport.model_fields["inclinations"]
        assert f.default is None

    def test_field_type_is_inclinations(self):
        from daypart.passport.view import HealthClonePassport
        from daypart.rm.inclinations import Inclinations

        ann = HealthClonePassport.model_fields["inclinations"].annotation
        assert Inclinations in getattr(ann, "__args__", (ann,))

    def test_research_passport_unchanged(self):
        import daypart.passport as p

        assert "inclinations" not in p.Passport.model_fields


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #


@pytest.mark.category("integration/passport-incl-api")
class TestApi:
    def test_syn_journal(self, client, syn_journal):
        body = _passport(client, syn_journal)
        assert "inclinations" in body
        _check_inc_json(body["inclinations"])

    def test_persona_journal(self, client, persona_journal):
        body = _passport(client, persona_journal)
        assert "inclinations" in body
        _check_inc_json(body["inclinations"])

    def test_syn_journal_day0(self, client, syn_journal):
        _check_inc_json(_passport(client, syn_journal, day=0)["inclinations"])

    def test_deterministic(self, client, syn_journal):
        a = _passport(client, syn_journal, day=0)["inclinations"]
        b = _passport(client, syn_journal, day=0)["inclinations"]
        assert a == b

    def test_other_cards_still_present(self, client, syn_journal):
        body = _passport(client, syn_journal)
        assert body["display_name"] == "Health Clone Passport"
        assert isinstance(body["cards"], list) and body["cards"]


# --------------------------------------------------------------------------- #
# Fail closed
# --------------------------------------------------------------------------- #


def _boom(*_a, **_k):
    raise RuntimeError("sealed: inclinations build failure")


@pytest.fixture
def broken_inclinations(monkeypatch):
    import daypart.rm.inclinations as inc_mod
    import daypart.rm.jev as jev_mod
    import daypart.rm.model as model_mod

    targets = {
        id(inc_mod.inclinations),
        id(model_mod.trained),
        id(jev_mod.answers_for),
        id(jev_mod.simulate_answers),
    }
    for name, mod in list(sys.modules.items()):
        if mod is None or not (name == "daypart" or name.startswith("daypart.")):
            continue
        for attr, val in list(vars(mod).items()):
            if id(val) in targets:
                monkeypatch.setattr(mod, attr, _boom)
    yield


@pytest.mark.category("integration/passport-incl-fail")
class TestFailClosed:
    @pytest.mark.parametrize("which", ["syn", "persona"])
    def test_null_and_rest_unchanged(self, client, syn_journal, persona_journal, request, which):
        jid = syn_journal if which == "syn" else persona_journal
        good = _passport(client, jid, day=0)
        assert good["inclinations"] is not None
        request.getfixturevalue("broken_inclinations")
        bad = _passport(client, jid, day=0)
        assert "inclinations" in bad and bad["inclinations"] is None
        good.pop("inclinations")
        bad.pop("inclinations")
        assert bad == good

    def test_recovers_after(self, client, syn_journal):
        _check_inc_json(_passport(client, syn_journal, day=0)["inclinations"])

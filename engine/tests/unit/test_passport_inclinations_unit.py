"""HAC-75: the passport's Inclinations section (API + view). Synthetic members only (I1)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from daypart.demo.app import create_app  # noqa: E402
from daypart.membrane import dsl  # noqa: E402
from daypart.passport import view  # noqa: E402
from syntropy.lhm.metrics.claims import assert_narration_safe  # noqa: E402

JARGON = re.compile(r"\b(logit|reward|grpo|rm|feature|intent|model|weights?|policy|latent)\b", re.IGNORECASE)
HTML = Path(view.__file__).resolve().parents[1] / "demo" / "static" / "index.html"


@pytest.fixture(scope="module")
def client():
    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("DAYPART_REAL_INPUT", raising=False)
        with TestClient(create_app(cohort_seed=0)) as c:
            yield c


def _passport(client, body):
    r = client.post("/api/journals", json=body)
    assert r.status_code == 201, r.text
    pp = client.get(f"/api/journals/{r.json()['journal_id']}/passport")
    assert pp.status_code == 200, pp.text
    return pp.json()


@pytest.mark.parametrize("body", [{"member_id": "syn-001"}, {"member_id": "syn-042"}, {"persona": "persona-v1"}])
def test_passport_has_inclinations(client, body):
    inc = _passport(client, body)["inclinations"]
    assert inc["title"] == "Inclinations" and inc["data"] == "synthetic"
    drivers = {d["driver_id"]: d for d in inc["drivers"]}
    assert 1 <= len(inc["insights"]) <= 3
    for ins in inc["insights"]:
        assert ins["driver"] in drivers  # each next step is linked to a shown driver
        assert ins["reason"].startswith("Why: ")
        assert ins["estimated_lift_points"] > 0
    for d in inc["drivers"]:
        assert d["direction"] in ("helps", "makes_harder") and 0 <= d["share"] <= 1


def test_inclinations_wording_is_safe_and_plain(client):
    inc = _passport(client, {"member_id": "syn-003"})["inclinations"]
    texts = [inc["note"], *(d["label"] for d in inc["drivers"])]
    texts += [t for i in inc["insights"] for t in (i["title"], i["action"], i["reason"])]
    for t in texts:
        assert_narration_safe(t)
        assert dsl.check(t).passed
        assert not JARGON.search(t), t
    assert "simulated" in inc["note"].lower()


def test_inclinations_are_deterministic(client):
    a = _passport(client, {"member_id": "syn-010"})["inclinations"]
    b = _passport(client, {"member_id": "syn-010"})["inclinations"]
    assert a == b


def test_inclinations_fail_closed(client, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("guard")

    monkeypatch.setattr("daypart.rm.inclinations.inclinations", boom)
    pp = _passport(client, {"member_id": "syn-001"})
    assert pp["inclinations"] is None
    assert pp["cards"]  # the rest of the passport still renders


def test_view_renders_inclinations_in_the_passport_section():
    html = HTML.read_text(encoding="utf-8")
    start, end = html.index('id="screen-passport"'), html.index('id="screen-next"')
    section = html[start:end]
    assert 'id="h-inclinations"' in section and 'id="pp-incl"' in section
    assert "function renderInclinations" in html and "renderInclinations(pp.inclinations)" in html
    assert "Linked to: " in html

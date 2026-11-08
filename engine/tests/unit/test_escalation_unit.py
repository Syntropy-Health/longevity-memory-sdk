"""Unit tests for Track B calibrated escalation (AIR-319 ``track-b-spec``)."""

from __future__ import annotations

import json

import pytest

from daypart.checkin.crisis import HANDOFF_TEXT
from daypart.escalation import (
    FEATURE_NAMES,
    MODEL_FEATURES,
    TAU_HIGH,
    TAU_LOW,
    Assessment,
    Calibrator,
    CuratedMemberError,
    Day,
    History,
    as_history,
    assess,
    decide,
    features,
    fit,
    training_rows,
    until,
)
from daypart.escalation import metrics as m
from daypart.escalation.evaluate import evaluate
from daypart.eval import POLICY_TEXT, load_runs, run
from daypart.membrane import dsl
from daypart.membrane.dsl import RULE_VERSION
from daypart.simmember.cohort import CURATED_PROFILES, generate
from daypart.simmember.manifest import CuratedLeakError


@pytest.fixture(scope="module")
def cohort():
    return generate(0)


@pytest.fixture(scope="module")
def cal(cohort):
    return fit(cohort, 0)


def _days(pattern: str, state: str = "engaged") -> list[Day]:
    return [Day(adhered=c == "1", state=state) for c in pattern]


# ------------------------------------------------------------------ history / features


def test_features_shape_and_determinism(cohort):
    traj = cohort.trajectories["syn-001"]
    f = features(traj)
    assert list(f) == list(FEATURE_NAMES) and all(isinstance(v, float) for v in f.values())
    assert f == features(traj) == features(list(traj.days)) == features(as_history(traj))
    assert f["days_observed"] == len(traj.days) and f["crisis_marker_hits"] == 0.0


def test_features_values():
    days = [
        Day(adhered=True, state="engaged", checkin=True, sentiment=0.5),
        Day(adhered=False, state="strained"),
        Day(adhered=False, state="lapsed", checkin=True, sentiment=-0.5),
        Day(adhered=False, state="lapsed"),
        Day(adhered=True, state="recovering"),
        Day(adhered=False, state="lapsed"),
    ]
    f = features(days)
    assert f["adherence_rate"] == pytest.approx(2 / 6)
    assert f["missed_days"] == 4 and f["longest_miss_streak"] == 3
    assert f["days_since_last_adherence"] == 1 and f["lapsed_entries"] == 2
    assert f["lapsed_fraction"] == pytest.approx(3 / 6) and f["checkin_rate"] == pytest.approx(2 / 6)
    assert f["mean_sentiment"] == 0.0 and f["min_sentiment"] == -0.5


def test_features_empty_history():
    f = features([])
    assert f["days_observed"] == 0 and f["days_since_last_adherence"] == 0
    assert all(v == 0.0 for v in f.values())
    assert features(_days("000"))["days_since_last_adherence"] == 3


def test_history_refuses_latents(cohort):
    prof = cohort.profiles[0]
    for bad in (prof, prof.latents, cohort, {"member_id": prof.member_id, "latents": prof.latents}):
        with pytest.raises(TypeError):
            features(bad)


def test_history_text_forms():
    crisis = "I want to end my life"
    for h in (
        crisis,
        {"days": _days("11"), "texts": [crisis]},
        (_days("11"), [crisis]),
        [{"adhered": True, "state": "engaged", "text": crisis}],
        History(tuple(_days("1")), (crisis,)),
    ):
        assert features(h)["crisis_marker_hits"] == 1.0, h
    assert features(as_history(_days("1"), texts="call 911 now"))["crisis_marker_hits"] == 1.0
    assert features({"days": _days("11"), "texts": ["walked 988 steps today"]})["crisis_marker_hits"] == 0.0


def test_until(cohort):
    traj = cohort.trajectories["syn-002"]
    assert len(until(traj, 9).days) == 10
    with pytest.raises(ValueError):
        until(traj, -1)


# ------------------------------------------------------------------ fit / I1


def test_fit_deterministic_and_bounded(cohort, cal):
    again = fit(cohort, 0)
    assert again == cal and again.version == cal.version
    assert cal.feature_names == MODEL_FEATURES and cal.n_members == 175 and cal.n_train == 175 * 3
    assert 0.0 < cal.base_rate < 1.0
    assert fit(generate(1), 1).version != cal.version


def test_fit_input_forms_agree(cohort):
    syn = cohort.training_profiles()[:20]
    pairs = [(p, cohort.trajectories[p.member_id]) for p in syn]
    a = fit(pairs, 0)
    assert fit(list(syn), 0) == a  # trajectory regenerated from (latents, seed)
    assert fit([p.member_id for p in syn], 0) == a  # ids looked up in generate(seed)
    assert fit([{"profile": p, "trajectory": cohort.trajectories[p.member_id]} for p in syn], 0) == a


@pytest.mark.parametrize(
    "members",
    [
        lambda c: list(c.profiles),
        lambda c: [CURATED_PROFILES[0]],
        lambda c: ["cur-001"],
        lambda c: [(CURATED_PROFILES[3], c.trajectories["cur-004"])],
        lambda c: [{"member_id": "cur-002"}],
        lambda c: [CURATED_PROFILES[0].model_copy(update={"member_id": "syn-999", "cohort": "synthetic"})],
    ],
)
def test_fit_refuses_curated(cohort, members):
    with pytest.raises(CuratedMemberError) as exc:
        fit(members(cohort), 0)
    assert isinstance(exc.value, CuratedLeakError) and isinstance(exc.value, ValueError)


def test_fit_rejects_bad_input(cohort):
    with pytest.raises(ValueError):
        fit([], 0)
    with pytest.raises(ValueError):
        fit(["syn-998"], 0)
    p = cohort.training_profiles()[0]
    with pytest.raises(ValueError):
        fit([(p, cohort.trajectories["syn-002"])], 0)


def test_training_rows_have_no_curated(cohort):
    rows = training_rows(cohort, 0)
    assert {r["member_id"][:4] for r in rows} == {"syn-"}
    assert {r["history_days"] for r in rows} == {14, 28, 42}


# ------------------------------------------------------------------ assess / decision rule


def test_assess_shape(cohort, cal):
    a = assess(cohort.trajectories["cur-001"], cal)
    assert isinstance(a, Assessment) and 0.0 <= a.p_escalate <= 1.0
    assert a.decision in ("escalate", "no_escalation", "abstain")
    assert len(a.reasons) == 3 and set(a.reasons) <= set(MODEL_FEATURES)
    assert a.rule_version == RULE_VERSION and a.calibrator_version == cal.version
    assert a == assess(cohort.trajectories["cur-001"], cal)


def test_crisis_hard_gate(cal):
    clean = {"days": _days("1" * 30), "texts": ["Walked after lunch, felt good."]}
    for text in ("I want to end my life", "I called the crisis line last night", "thinking about suicide"):
        a = assess({"days": _days("1" * 30), "texts": [text]}, cal)
        assert (a.p_escalate, a.decision, a.reasons, a.text) == (1.0, "escalate", ["crisis_marker_hits"], HANDOFF_TEXT)
        assert dsl.check(a.text, crisis_context=True).passed
    assert assess(clean, cal).reasons != ["crisis_marker_hits"]


def _forced(intercept: float) -> Calibrator:
    n = len(MODEL_FEATURES)
    return Calibrator(MODEL_FEATURES, (0.0,) * n, (1.0,) * n, (0.0,) * n, intercept, 0.5, 1, 1, 0)


@pytest.mark.parametrize(
    "z,decision",
    [(3.0, "escalate"), (-3.0, "no_escalation"), (0.0, "abstain")],
)
def test_tau_band(z, decision):
    a = assess(_days("1010"), _forced(z))
    assert a.decision == decision
    assert a.text == (POLICY_TEXT["clinician_handoff"] if decision == "escalate" else None)
    if a.text:
        assert dsl.check(a.text).passed


def test_decide_edges():
    assert decide(TAU_HIGH) == "escalate" and decide(TAU_LOW) == "no_escalation"
    assert decide((TAU_LOW + TAU_HIGH) / 2) == "abstain"
    assert decide(1.0) == "escalate" and decide(0.0) == "no_escalation"


def test_assess_needs_calibrator():
    with pytest.raises(TypeError):
        assess(_days("1"), None)  # type: ignore[arg-type]


def test_assessment_range():
    with pytest.raises(ValueError):
        Assessment(p_escalate=1.5, decision="abstain", reasons=[], rule_version="x", calibrator_version="y")


# ------------------------------------------------------------------ metrics


def test_brier_ece_reliability():
    p, y = [0.0, 1.0, 0.25, 0.75], [False, True, False, True]
    assert m.brier(p, y) == pytest.approx(0.03125)
    assert m.ece(p, y) == pytest.approx(0.125)
    rel = m.reliability(p, y)
    assert len(rel) == 10 and sum(r["n"] for r in rel) == 4 and rel[9]["n"] == 1
    assert rel[2] == {"bin": 2, "lo": 0.2, "hi": 0.3, "n": 1, "mean_p": 0.25, "frac_positive": 0.0}
    assert rel[5]["mean_p"] is None
    assert m.brier([], []) is None and m.ece([], []) is None
    with pytest.raises(ValueError):
        m.brier([0.5], [])
    with pytest.raises(ValueError):
        m.ece([1.2], [True])


def test_decision_metrics():
    d = m.decision_metrics(["escalate", "escalate", "abstain", "no_escalation"], [True, False, True, False])
    assert d["precision"] == 0.5 and d["recall"] == 0.5 and d["abstention_rate"] == 0.25
    none = m.decision_metrics(["abstain"], [False])
    assert none["precision"] is None and none["recall"] is None


# ------------------------------------------------------------------ eval arm


def test_evaluate_deterministic_and_complete():
    a = evaluate([0, 1], history_days=14)
    assert a == evaluate([0, 1], history_days=14)
    assert a["n"] == 50 and len(a["per_seed"]) == 2 and a["heldout"] == "curated-25"
    for key in ("brier", "ece", "reliability", "abstention_rate", "precision", "recall", "base_rate"):
        assert key in a
    assert len(a["reliability"]) == 10 and a["text_checks"]["n"] == a["text_checks"]["passed"]
    assert a["beats_base_rate"]["brier"] == (a["brier"] < a["base_rate"]["brier"])
    json.dumps(a)
    with pytest.raises(ValueError):
        evaluate([])


def test_default_run_has_escalation_arm():
    doc = run(load_runs())
    arm = next(x for x in doc["arms"] if x["name"] == "escalation")
    assert arm["kind"] == "escalation" and arm["status"] == "ok"
    assert arm["metrics"]["n"] == 75 and arm["metrics"]["seeds"] == [0, 1, 2]


# ------------------------------------------------------------------ QG findings (AIR-322 gate 1)


def _renamed_curated() -> dict:
    return CURATED_PROFILES[0].model_copy(update={"member_id": "syn-999", "cohort": "synthetic"}).model_dump(mode="json")


@pytest.mark.parametrize(
    "form",
    [lambda d: d, lambda d: {"profile": d}, lambda d: (d, None)],
    ids=["flat_dict", "profile_key", "tuple"],
)
def test_qg_f1_fit_refuses_curated_latents_in_dicts(form):
    with pytest.raises(CuratedMemberError, match="syn-999"):
        fit([form(_renamed_curated())], 0)
    with pytest.raises(CuratedMemberError):
        training_rows([form(_renamed_curated())], 0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), "nan"])
def test_qg_f3_non_finite_sentiment_never_silences(cal, bad):
    days = [{"adhered": False, "state": "lapsed", "checkin": True, "sentiment": bad}] * 20
    with pytest.raises(ValueError):
        assess(days, cal)


def test_qg_f3_assessment_rejects_nan():
    with pytest.raises(ValueError):
        Assessment(p_escalate=float("nan"), decision="abstain", reasons=[], rule_version="x", calibrator_version="y")


@pytest.mark.parametrize("n", [0, 1, 7, 13])
def test_qg_f4_short_history_abstains(cal, n):
    for h in (_days("0" * n, state="lapsed"), {"days": _days("1" * n), "texts": ["Walked after lunch."]}):
        a = assess(h, cal)
        assert a.decision == "abstain" and a.text is None and a.reasons == ["days_observed"]
        assert a.p_escalate == pytest.approx(cal.base_rate)


def test_qg_f4_crisis_gate_still_fires_on_short_history(cal):
    assert assess("I want to end my life", cal).decision == "escalate"
    assert assess(_days("1" * 14), cal).reasons != ["days_observed"]

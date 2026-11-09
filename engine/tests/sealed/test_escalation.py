"""Sealed challenge suite: Track B calibrated escalation (``daypart.escalation``).

Written double-blind from AIR-319 document ``track-b-spec`` (contract v1) only.
The implementation (``engine/daypart/escalation/``) was never read.

Categories (``@pytest.mark.category``):
  functional/esc-interface    module surface, thresholds, Assessment shape and value ranges
  functional/esc-features     features(): deterministic, observables only, prefix-only (day t)
  functional/esc-decision     decision rule: tau_high / abstain band / tau_low
  functional/esc-crisis-gate  crisis-marker hard gate (boundary-v1 markers -> escalate, p = 1.0)
  functional/esc-determinism  same seed -> same calibrator and same numbers
  functional/esc-i1           fit() refuses curated (held-out) members (invariant I1)
  functional/esc-membrane     every emitted text passes membrane.dsl.check()
  functional/esc-offline      no network during fit/assess
  integration/esc-eval-arm    escalation arm in ``python -m daypart.eval`` / metrics.json

Shapes the spec leaves open, pinned here and posted to the CTO on AIR-323 (one adapter each):
  * history:  ``history_from(trajectory, day, texts=()) -> History``, observable days 0..day
    inclusive plus check-in texts. Tests build histories only through it.
  * fit:      ``fit(members: Sequence[tuple[Profile, Trajectory]], seed)``; curated -> raises
    ``CuratedLeakError`` or ``ValueError``.
  * tau:      module constants ``TAU_LOW`` / ``TAU_HIGH``.
  * text:     ``Assessment.text: str | None``; on escalate it is POLICY_TEXT["clinician_handoff"].
  * eval arm: a runs.yaml arm whose name or kind contains "escalation"; metric names are matched
    by substring (brier, ece/calibration_error, reliab*, abstention, precision, recall, base*).
"""

from __future__ import annotations

import json
import math
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parents[2]
DECISIONS = {"escalate", "no_escalation", "abstain"}
SAMPLE_DAYS = (0, 6, 13, 20, 27, 41)
NEUTRAL_TEXTS = ("Busy week, walked twice and slept fine.", "Skipped yesterday, back on it today.")


# --------------------------------------------------------------------------- #
# adapters + fixtures
# --------------------------------------------------------------------------- #


def _esc():
    import daypart.escalation as esc

    return esc


def _history(traj, day, texts=()):
    return _esc().history_from(traj, day, texts=tuple(texts))


def _members(cohort, kind):
    return [(p, cohort.trajectories[p.member_id]) for p in cohort.profiles if p.cohort == kind]


def _days(traj):
    n = len(traj.days)
    return sorted({d for d in SAMPLE_DAYS if d < n} | {n - 1})


def _crisis_markers():
    from daypart.membrane import dsl

    return tuple(dsl.load_rules(dsl.RULE_VERSION).crisis_markers)


def _marker_text(marker):
    return f"Rough night. I ended up calling the {marker} and talked for a while."


def _rehome(traj, new_id):
    """Same observable days under another member id (note ids follow the id)."""
    from daypart.simmember.trajectory import Trajectory

    days = tuple(
        d.model_copy(update={"note_id": f"note:{new_id}:d{d.day}"}) if d.note_id else d for d in traj.days
    )
    return Trajectory(member_id=new_id, days=days)


def _strings(obj):
    """Every str value reachable from an Assessment (attributes, dicts, lists)."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for v in obj:
            yield from _strings(v)
    elif hasattr(obj, "model_dump"):
        yield from _strings(obj.model_dump())
    elif hasattr(obj, "__dataclass_fields__"):
        for name in obj.__dataclass_fields__:
            yield from _strings(getattr(obj, name))


@pytest.fixture(scope="module")
def synthetic(cohort0):
    return _members(cohort0, "synthetic")


@pytest.fixture(scope="module")
def curated(cohort0):
    return _members(cohort0, "curated")


@pytest.fixture(scope="module")
def calibrator(synthetic):
    return _esc().fit(synthetic, seed=0)


@pytest.fixture(scope="module")
def assessments(calibrator, cohort0):
    """(member_id, day, Assessment) for every member at the sample days, no texts."""
    esc = _esc()
    out = []
    for p in cohort0.profiles:
        traj = cohort0.trajectories[p.member_id]
        for day in _days(traj):
            out.append((p.member_id, day, esc.assess(_history(traj, day), calibrator)))
    return out


@pytest.fixture(scope="module")
def low_risk(curated, calibrator):
    """A held-out member/day the model alone does NOT escalate (lowest p)."""
    esc = _esc()
    best = None
    for p, traj in curated:
        for day in _days(traj):
            a = esc.assess(_history(traj, day, NEUTRAL_TEXTS), calibrator)
            if best is None or a.p_escalate < best[2].p_escalate:
                best = (traj, day, a)
    assert best[2].decision != "escalate", "every curated member escalates without a marker; gate untestable"
    return best


# --------------------------------------------------------------------------- #
# interface shape and value ranges
# --------------------------------------------------------------------------- #


@pytest.mark.category("functional/esc-interface")
def test_module_surface():
    """Spec 'Interface': features, fit, assess (+ pinned history_from, TAU_LOW/HIGH)."""
    esc = _esc()
    for name in ("features", "fit", "assess", "history_from", "TAU_LOW", "TAU_HIGH"):
        assert hasattr(esc, name), f"daypart.escalation.{name} missing"
    for name in ("features", "fit", "assess", "history_from"):
        assert callable(getattr(esc, name))


@pytest.mark.category("functional/esc-interface")
def test_thresholds_are_fixed_ordered_constants():
    """Spec 'Decision rule': tau values are fixed constants with tau_low < tau_high in (0, 1)."""
    esc = _esc()
    lo, hi = esc.TAU_LOW, esc.TAU_HIGH
    assert isinstance(lo, float) and isinstance(hi, float)
    assert 0.0 < lo < hi < 1.0


@pytest.mark.category("functional/esc-interface")
def test_thresholds_not_tuned_by_fit(synthetic):
    """Spec: tau values are fixed constants, not tuned (fit must not move them)."""
    esc = _esc()
    before = (esc.TAU_LOW, esc.TAU_HIGH)
    esc.fit(synthetic, seed=1)
    esc.fit(synthetic, seed=2)
    assert (esc.TAU_LOW, esc.TAU_HIGH) == before


@pytest.mark.category("functional/esc-interface")
def test_assessment_fields_and_ranges(assessments):
    """Spec 'assess': p in [0,1], decision enum, reasons list[str], version strings."""
    assert assessments
    for mid, day, a in assessments:
        p = a.p_escalate
        assert isinstance(p, float) and not isinstance(p, bool), (mid, day, type(p))
        assert math.isfinite(p) and 0.0 <= p <= 1.0, (mid, day, p)
        assert a.decision in DECISIONS, (mid, day, a.decision)
        assert isinstance(a.reasons, list) and all(isinstance(r, str) and r for r in a.reasons), (mid, day)
        assert isinstance(a.rule_version, str) and a.rule_version.strip()
        assert isinstance(a.calibrator_version, str) and a.calibrator_version.strip()


@pytest.mark.category("functional/esc-interface")
def test_reasons_are_feature_names(cohort0, calibrator):
    """Spec: reasons are the feature names that drove the decision."""
    esc = _esc()
    for p in cohort0.heldout_profiles():
        traj = cohort0.trajectories[p.member_id]
        for day in _days(traj):
            h = _history(traj, day)
            names = set(esc.features(h))
            a = esc.assess(h, calibrator)
            assert set(a.reasons) <= names, (p.member_id, day, set(a.reasons) - names)


@pytest.mark.category("functional/esc-interface")
def test_versions_stable_across_members(assessments):
    """One calibrator, one rule: rule_version and calibrator_version do not vary per member."""
    assert len({a.rule_version for _, _, a in assessments}) == 1
    assert len({a.calibrator_version for _, _, a in assessments}) == 1


# --------------------------------------------------------------------------- #
# features: deterministic, observables only, up to day t
# --------------------------------------------------------------------------- #


@pytest.mark.category("functional/esc-features")
def test_features_shape_and_determinism(cohort0):
    """Spec 'features': dict[str, float], deterministic, same key set for every history."""
    esc = _esc()
    keys = None
    for p in cohort0.profiles[:60]:
        traj = cohort0.trajectories[p.member_id]
        for day in _days(traj):
            f1 = esc.features(_history(traj, day))
            f2 = esc.features(_history(traj, day))
            assert isinstance(f1, dict) and f1, (p.member_id, day)
            assert f1 == f2
            for k, v in f1.items():
                assert isinstance(k, str) and k
                assert isinstance(v, float) and not isinstance(v, bool), (k, type(v))
                assert math.isfinite(v), (k, v)
            keys = set(f1) if keys is None else keys
            assert set(f1) == keys, "feature key set must not depend on the member"


@pytest.mark.category("functional/esc-features")
def test_features_ignore_days_after_t(cohort0, calibrator):
    """Spec: observables 'up to day t' only. Rewriting days > t changes nothing at day t."""
    from daypart.simmember.trajectory import Trajectory

    esc = _esc()
    for p in cohort0.heldout_profiles()[:10]:
        traj = cohort0.trajectories[p.member_id]
        t = min(13, len(traj.days) - 2)
        future = tuple(
            d.model_copy(update={"state": "lapsed", "adhered": False, "checkin": False, "sentiment": None, "note_id": None})
            if d.day > t else d
            for d in traj.days
        )
        altered = Trajectory(member_id=traj.member_id, days=future)
        assert esc.features(_history(traj, t)) == esc.features(_history(altered, t))
        assert esc.assess(_history(traj, t), calibrator).p_escalate == esc.assess(
            _history(altered, t), calibrator
        ).p_escalate


@pytest.mark.category("functional/esc-features")
def test_estimator_never_reads_latents(cohort0, calibrator):
    """Spec 'Ground truth': the estimator never reads latents. The same observable days under a
    member id whose hidden escalation_trigger differs must score identically."""
    esc = _esc()
    synth = cohort0.training_profiles()
    with_trigger = next(p for p in synth if p.latents.escalation_trigger != "none")
    without = next(p for p in synth if p.latents.escalation_trigger == "none")
    for src, dst in ((with_trigger, without), (without, with_trigger)):
        traj = cohort0.trajectories[src.member_id]
        moved = _rehome(traj, dst.member_id)
        for day in _days(traj):
            a, b = esc.features(_history(traj, day)), esc.features(_history(moved, day))
            assert a == b, (src.member_id, dst.member_id, day)
            pa = esc.assess(_history(traj, day), calibrator).p_escalate
            pb = esc.assess(_history(moved, day), calibrator).p_escalate
            assert pa == pb


@pytest.mark.category("functional/esc-features")
def test_features_no_simulator_regeneration(cohort0, calibrator, monkeypatch):
    """Observables only: features/assess must not regenerate the cohort to look up latents."""
    import daypart.simmember.cohort as cohort_mod
    import daypart.simmember.trajectory as traj_mod

    esc = _esc()
    p = cohort0.heldout_profiles()[0]
    traj = cohort0.trajectories[p.member_id]
    h = _history(traj, 13)

    def _boom(*a, **k):
        raise AssertionError("escalation read the simulator (latents) at assess time")

    monkeypatch.setattr(cohort_mod, "generate", _boom)
    monkeypatch.setattr(traj_mod, "generate_trajectory", _boom)
    esc.features(h)
    esc.assess(h, calibrator)


@pytest.mark.category("functional/esc-features")
def test_crisis_marker_feature_moves(low_risk):
    """Spec 'features': crisis-marker hits are a feature; a marker text must change the features."""
    esc = _esc()
    traj, day, _ = low_risk
    plain = esc.features(_history(traj, day, NEUTRAL_TEXTS))
    hit = esc.features(_history(traj, day, NEUTRAL_TEXTS + (_marker_text("crisis line"),)))
    assert plain != hit


# --------------------------------------------------------------------------- #
# decision rule: escalate / abstain band / no_escalation
# --------------------------------------------------------------------------- #


@pytest.mark.category("functional/esc-decision")
def test_decision_follows_thresholds(assessments):
    """Spec 'Decision rule' (no crisis marker): p >= tau_high -> escalate; p <= tau_low ->
    no_escalation; strictly between -> abstain."""
    esc = _esc()
    for mid, day, a in assessments:
        p = a.p_escalate
        if p >= esc.TAU_HIGH:
            want = "escalate"
        elif p <= esc.TAU_LOW:
            want = "no_escalation"
        else:
            want = "abstain"
        assert a.decision == want, (mid, day, p, a.decision)


@pytest.mark.category("functional/esc-decision")
def test_abstain_band_is_exactly_the_open_interval(assessments):
    """Spec: abstain <=> tau_low < p < tau_high; abstain never carries p outside the band."""
    esc = _esc()
    for mid, day, a in assessments:
        in_band = esc.TAU_LOW < a.p_escalate < esc.TAU_HIGH
        assert (a.decision == "abstain") == in_band, (mid, day, a.p_escalate, a.decision)


@pytest.mark.category("functional/esc-decision")
def test_model_not_degenerate(assessments):
    """A calibrated model fit on 175 profiles does not emit one constant p for every member/day."""
    assert len({round(a.p_escalate, 9) for _, _, a in assessments}) > 1


@pytest.mark.category("functional/esc-decision")
def test_neutral_text_does_not_trip_gate(low_risk, calibrator):
    """Gate is marker-driven: ordinary check-in text never forces escalate with p = 1.0."""
    esc = _esc()
    traj, day, _ = low_risk
    a = esc.assess(_history(traj, day, NEUTRAL_TEXTS), calibrator)
    assert a.decision != "escalate"
    assert a.p_escalate < 1.0


# --------------------------------------------------------------------------- #
# crisis-marker hard gate
# --------------------------------------------------------------------------- #


@pytest.mark.category("functional/esc-crisis-gate")
def test_pack_has_crisis_markers():
    """Precondition: the boundary-v1 pack exposes the crisis markers the gate uses."""
    assert len(_crisis_markers()) >= 1


@pytest.mark.category("functional/esc-crisis-gate")
@pytest.mark.parametrize("marker", _crisis_markers())
def test_every_pack_marker_forces_escalate(marker, low_risk, calibrator):
    """Spec 'Decision rule': a crisis-marker hit -> escalate with p_escalate = 1.0, whatever
    the model says (tested on the lowest-risk held-out member/day)."""
    esc = _esc()
    traj, day, _ = low_risk
    a = esc.assess(_history(traj, day, NEUTRAL_TEXTS + (_marker_text(marker),)), calibrator)
    assert a.decision == "escalate", (marker, a.decision)
    assert a.p_escalate == 1.0, (marker, a.p_escalate)
    assert a.reasons, "an escalation must name what drove it"


@pytest.mark.category("functional/esc-crisis-gate")
@pytest.mark.parametrize(
    "text",
    [
        "I CALLED THE CRISIS LINE LAST NIGHT.",
        "Talked to the  Crisis   Text   Line for an hour.",
        "had to phone emergency services",
    ],
)
def test_gate_survives_case_and_spacing(text, low_risk, calibrator):
    """Markers are matched via membrane.dsl normalisation: case and whitespace cannot hide them."""
    esc = _esc()
    traj, day, _ = low_risk
    a = esc.assess(_history(traj, day, (text,)), calibrator)
    assert (a.decision, a.p_escalate) == ("escalate", 1.0)


@pytest.mark.category("functional/esc-crisis-gate")
def test_gate_holds_for_every_member(cohort0, calibrator):
    """Hard gate, whatever the model says: every member/day with a marker text escalates."""
    esc = _esc()
    text = _marker_text("crisis line")
    for p in cohort0.profiles[::7]:
        traj = cohort0.trajectories[p.member_id]
        for day in (0, len(traj.days) - 1):
            a = esc.assess(_history(traj, day, (text,)), calibrator)
            assert (a.decision, a.p_escalate) == ("escalate", 1.0), (p.member_id, day)


@pytest.mark.category("functional/esc-crisis-gate")
def test_marker_among_many_texts(low_risk, calibrator):
    """One marker anywhere in the check-in texts is enough."""
    esc = _esc()
    traj, day, _ = low_risk
    texts = NEUTRAL_TEXTS * 5 + (_marker_text("emergency number"),) + NEUTRAL_TEXTS
    a = esc.assess(_history(traj, day, texts), calibrator)
    assert (a.decision, a.p_escalate) == ("escalate", 1.0)


# --------------------------------------------------------------------------- #
# determinism per seed
# --------------------------------------------------------------------------- #


@pytest.mark.category("functional/esc-determinism")
def test_same_seed_same_numbers(synthetic, curated):
    """Spec 'Done when': same seed -> same numbers (two fits, identical p and decisions)."""
    esc = _esc()
    c1 = esc.fit(synthetic, seed=0)
    c2 = esc.fit(synthetic, seed=0)
    for p, traj in curated:
        for day in _days(traj):
            a, b = esc.assess(_history(traj, day), c1), esc.assess(_history(traj, day), c2)
            assert (a.p_escalate, a.decision, a.reasons, a.calibrator_version) == (
                b.p_escalate,
                b.decision,
                b.reasons,
                b.calibrator_version,
            ), (p.member_id, day)


@pytest.mark.category("functional/esc-determinism")
def test_determinism_across_processes(tmp_path):
    """Same seed -> same numbers in a fresh interpreter (no hash-seed or global-state drift)."""
    script = tmp_path / "probe.py"
    script.write_text(
        "import json\n"
        "import daypart.escalation as esc\n"
        "from daypart.simmember.cohort import generate\n"
        "c = generate(0)\n"
        "m = [(p, c.trajectories[p.member_id]) for p in c.profiles if p.cohort == 'synthetic']\n"
        "cal = esc.fit(m, seed=0)\n"
        "out = []\n"
        "for p in c.profiles:\n"
        "    if p.cohort != 'curated':\n"
        "        continue\n"
        "    t = c.trajectories[p.member_id]\n"
        "    a = esc.assess(esc.history_from(t, len(t.days) - 1, texts=()), cal)\n"
        "    out.append([p.member_id, a.p_escalate, a.decision, a.calibrator_version])\n"
        "print(json.dumps(out))\n",
        encoding="utf-8",
    )
    runs = []
    for hashseed in ("0", "12345"):
        r = subprocess.run(
            [sys.executable, str(script)],
            cwd=ENGINE,
            capture_output=True,
            text=True,
            timeout=600,
            env={**__import__("os").environ, "PYTHONHASHSEED": hashseed},
        )
        assert r.returncode == 0, r.stderr[-2000:]
        runs.append(json.loads(r.stdout.strip().splitlines()[-1]))
    assert runs[0] == runs[1]
    assert len(runs[0]) == 25


# --------------------------------------------------------------------------- #
# I1: fit refuses curated (held-out) ids
# --------------------------------------------------------------------------- #


def _leak_errors():
    from daypart.simmember.manifest import CuratedLeakError

    return (CuratedLeakError, ValueError)


@pytest.mark.category("functional/esc-i1")
def test_cohort_split_sizes(synthetic, curated):
    """Spec: fit on the 175 generated profiles; evaluate on the 25 curated."""
    assert len(synthetic) == 175
    assert len(curated) == 25


@pytest.mark.category("functional/esc-i1")
def test_fit_accepts_synthetic_only(synthetic):
    """fit on the 175 generated profiles succeeds and returns a usable calibrator."""
    cal = _esc().fit(synthetic, seed=0)
    assert cal is not None


@pytest.mark.category("functional/esc-i1")
def test_fit_refuses_all_curated(curated):
    """Invariant I1: fit raises if curated (held-out) members are passed."""
    with pytest.raises(_leak_errors()):
        _esc().fit(curated, seed=0)


@pytest.mark.category("functional/esc-i1")
@pytest.mark.parametrize("position", ["first", "middle", "last"])
def test_fit_refuses_one_curated_among_synthetic(position, synthetic, curated):
    """Invariant I1: a single curated member anywhere in the list is refused."""
    leak = curated[3]
    members = list(synthetic)
    idx = {"first": 0, "middle": len(members) // 2, "last": len(members)}[position]
    members.insert(idx, leak)
    with pytest.raises(_leak_errors()):
        _esc().fit(members, seed=0)


@pytest.mark.category("functional/esc-i1")
def test_fit_refuses_curated_given_as_iterator(synthetic, curated):
    """Refusal does not depend on the container type (a one-shot generator still trips it)."""
    gen = (m for m in list(synthetic[:20]) + [curated[0]])
    with pytest.raises(_leak_errors()):
        _esc().fit(gen, seed=0)


@pytest.mark.category("functional/esc-i1")
def test_fit_refuses_curated_trajectory_under_synthetic_profile(synthetic, curated):
    """A curated trajectory (cur- id) smuggled next to a synthetic profile is refused too."""
    p_syn, _ = synthetic[0]
    _, t_cur = curated[0]
    members = list(synthetic[1:]) + [(p_syn, t_cur)]
    with pytest.raises(_leak_errors()):
        _esc().fit(members, seed=0)


@pytest.mark.category("functional/esc-i1")
def test_i1_check_passes():
    """Spec 'Done when': CI i1_check passes with the escalation subsystem present."""
    r = subprocess.run(
        [sys.executable, "-m", "daypart.ci.i1_check"], cwd=ENGINE, capture_output=True, text=True, timeout=600
    )
    assert r.returncode == 0, (r.stdout[-2000:], r.stderr[-2000:])


# --------------------------------------------------------------------------- #
# emitted text passes membrane.dsl.check()
# --------------------------------------------------------------------------- #


@pytest.mark.category("functional/esc-membrane")
def test_all_emitted_strings_pass_dsl(assessments, low_risk, calibrator):
    """Spec: any text the subsystem emits passes membrane.dsl.check()."""
    from daypart.membrane import dsl

    esc = _esc()
    traj, day, _ = low_risk
    crisis = [esc.assess(_history(traj, day, (_marker_text(m),)), calibrator) for m in _crisis_markers()]
    for a in [a for _, _, a in assessments] + crisis:
        for s in _strings(a):
            v = dsl.check(s)
            assert v.passed, (s, [x.rule_id for x in v.violations])


@pytest.mark.category("functional/esc-membrane")
def test_escalate_text_is_clinician_handoff(low_risk, calibrator, assessments):
    """Spec: the escalate text is the existing clinician_handoff policy text."""
    from daypart.eval import POLICY_TEXT

    esc = _esc()
    traj, day, _ = low_risk
    escalations = [esc.assess(_history(traj, day, (_marker_text("crisis line"),)), calibrator)]
    escalations += [a for _, _, a in assessments if a.decision == "escalate"]
    for a in escalations:
        assert a.text == POLICY_TEXT["clinician_handoff"]


@pytest.mark.category("functional/esc-membrane")
def test_non_escalate_text_is_none_or_safe(assessments):
    """Non-escalate decisions emit no text, or text that passes the membrane."""
    from daypart.membrane import dsl

    for _, _, a in assessments:
        if a.decision != "escalate":
            assert a.text is None or dsl.check(a.text).passed


@pytest.mark.category("functional/esc-membrane")
def test_emitted_text_never_echoes_member_text(low_risk, calibrator):
    """The subsystem never parrots member check-in text (could carry medical content)."""
    esc = _esc()
    traj, day, _ = low_risk
    member = "Doctor said take 50 mg of sertraline twice daily for my depression."
    for texts in ((member,), (member, _marker_text("crisis line"))):
        a = esc.assess(_history(traj, day, texts), calibrator)
        for s in _strings(a):
            assert "sertraline" not in s.lower() and "50 mg" not in s.lower(), s


# --------------------------------------------------------------------------- #
# offline: no keys, no network
# --------------------------------------------------------------------------- #


@pytest.mark.category("functional/esc-offline")
def test_fit_and_assess_offline(synthetic, curated, monkeypatch):
    """Spec 'Done when': offline, no keys. Any socket connect during fit/assess fails the test."""
    for var in ("MUSE_API_KEY", "MUSE_BASE_URL", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "MODAL_TOKEN_ID"):
        monkeypatch.delenv(var, raising=False)

    def _no_net(*a, **k):
        raise AssertionError("network access during escalation fit/assess")

    monkeypatch.setattr(socket.socket, "connect", _no_net)
    monkeypatch.setattr(socket, "create_connection", _no_net)
    esc = _esc()
    cal = esc.fit(synthetic, seed=0)
    for p, traj in curated[:5]:
        esc.assess(_history(traj, len(traj.days) - 1), cal)


# --------------------------------------------------------------------------- #
# eval arm in python -m daypart.eval / metrics.json
# --------------------------------------------------------------------------- #


def _is_esc_arm(arm) -> bool:
    name = arm["name"] if isinstance(arm, dict) else arm.name
    kind = arm["kind"] if isinstance(arm, dict) else arm.kind
    return "escalation" in f"{name} {kind}".lower()


def _paths(obj, prefix=""):
    """Flatten nested metric keys to lowercase dotted paths."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}".lower() if prefix else str(k).lower()
            yield p, v
            yield from _paths(v, p)


def _find(metrics, *needles):
    return [(p, v) for p, v in _paths(metrics) if any(n in p.rsplit(".", 1)[-1] for n in needles)]


@pytest.fixture(scope="module")
def esc_arm_config():
    import daypart.eval.models as models

    config = models.load_runs()
    arms = [a for a in config.arms if _is_esc_arm(a)]
    assert len(arms) == 1, f"default runs.yaml must carry exactly one escalation arm, got {[a.name for a in arms]}"
    return config, arms[0]


@pytest.fixture(scope="module")
def esc_arm_result(esc_arm_config):
    from daypart.eval import harness
    from daypart.eval.models import RunsConfig

    config, arm = esc_arm_config
    only = RunsConfig(version=config.version, cohort_seed=config.cohort_seed, arms=(arm,))
    return harness.run(only, root=ENGINE)["arms"][0]


@pytest.mark.category("integration/esc-eval-arm")
def test_arm_status_is_honest(esc_arm_result):
    """Spec 'Evaluation': written like every other arm; ok, or not_run/failed with a reason."""
    r = esc_arm_result
    assert r["status"] in {"ok", "not_run", "failed"}
    if r["status"] == "ok":
        assert isinstance(r["metrics"], dict) and r["metrics"]
    else:
        assert isinstance(r["reason"], str) and r["reason"].strip()
        assert not r["metrics"], "a not_run/failed arm must not report numbers"


@pytest.mark.category("integration/esc-eval-arm")
def test_arm_runs_ok_offline(esc_arm_result):
    """Spec 'Done when': offline, no keys, no GPU, so the arm runs in CI (status ok)."""
    assert esc_arm_result["status"] == "ok", esc_arm_result.get("reason")


@pytest.mark.category("integration/esc-eval-arm")
def test_arm_named_metrics_and_ranges(esc_arm_result):
    """Spec 'Evaluation': Brier, ECE (10 bins), reliability table, abstention rate,
    precision/recall of escalate, compared with a constant base-rate predictor."""
    if esc_arm_result["status"] != "ok":
        pytest.fail(f"arm not ok: {esc_arm_result['status']}: {esc_arm_result.get('reason')}")
    m = esc_arm_result["metrics"]
    required = {
        "brier": ("brier",),
        "ece": ("ece", "calibration_error"),
        "reliability": ("reliab",),
        "abstention": ("abstain", "abstention"),
        "precision": ("precision",),
        "recall": ("recall",),
        "base_rate": ("base_rate", "baseline", "base"),
    }
    for label, needles in required.items():
        assert _find(m, *needles), f"metrics.json escalation arm has no {label} metric: {sorted(p for p, _ in _paths(m))}"

    for p, v in _find(m, "brier", "ece", "calibration_error", "abstention_rate", "abstain_rate", "precision", "recall"):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            assert 0.0 <= v <= 1.0 and math.isfinite(v), (p, v)
        else:
            assert v is None or isinstance(v, (dict, list)), (p, v)


@pytest.mark.category("integration/esc-eval-arm")
def test_reliability_table_has_ten_bins(esc_arm_result):
    """Spec: ECE over 10 equal-width bins, with a reliability-bin table."""
    if esc_arm_result["status"] != "ok":
        pytest.fail(f"arm not ok: {esc_arm_result.get('reason')}")
    tables = [v for p, v in _find(esc_arm_result["metrics"], "reliab") if isinstance(v, (list, dict))]
    assert tables, "no reliability table"
    t = tables[0]
    rows = t if isinstance(t, list) else next((v for v in t.values() if isinstance(v, list)), list(t.values()))
    assert len(rows) == 10, f"expected 10 equal-width bins, got {len(rows)}"


@pytest.mark.category("integration/esc-eval-arm")
def test_base_rate_comparison_has_brier(esc_arm_result):
    """Spec: compared with a constant base-rate predictor, so the baseline carries its own Brier."""
    if esc_arm_result["status"] != "ok":
        pytest.fail(f"arm not ok: {esc_arm_result.get('reason')}")
    m = esc_arm_result["metrics"]
    briers = [(p, v) for p, v in _find(m, "brier") if isinstance(v, (int, float))]
    assert any("base" in p for p, _ in briers), f"no base-rate Brier among {briers}"
    assert any("base" not in p for p, _ in briers), f"no model Brier among {briers}"


@pytest.mark.category("integration/esc-eval-arm")
def test_arm_deterministic(esc_arm_config, esc_arm_result):
    """Spec 'Done when': same seed -> same numbers in metrics.json."""
    from daypart.eval import harness
    from daypart.eval.models import RunsConfig

    config, arm = esc_arm_config
    only = RunsConfig(version=config.version, cohort_seed=config.cohort_seed, arms=(arm,))
    again = harness.run(only, root=ENGINE)["arms"][0]
    assert harness.dumps(again) == harness.dumps(esc_arm_result)


@pytest.mark.category("integration/esc-eval-arm")
def test_cli_writes_arm_to_metrics_json(esc_arm_config, tmp_path):
    """Spec: an arm in `python -m daypart.eval`, written to metrics.json like every other arm."""
    import yaml

    config, arm = esc_arm_config
    runs = tmp_path / "runs.yaml"
    runs.write_text(
        yaml.safe_dump(
            {
                "version": config.version,
                "cohort_seed": config.cohort_seed,
                "arms": [arm.model_dump(mode="json", exclude_defaults=True) | {"name": arm.name, "kind": arm.kind}],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "metrics.json"
    r = subprocess.run(
        [sys.executable, "-m", "daypart.eval", "--runs", str(runs), "--out", str(out), "--root", str(ENGINE)],
        cwd=ENGINE,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert out.is_file(), r.stderr[-2000:]
    data = json.loads(out.read_text(encoding="utf-8"))
    arms = [a for a in data["arms"] if _is_esc_arm(a)]
    assert len(arms) == 1
    assert arms[0]["status"] in {"ok", "not_run", "failed"}
    assert r.returncode == (1 if arms[0]["status"] == "failed" else 0)


@pytest.mark.category("integration/esc-eval-arm")
def test_default_eval_lists_escalation_arm_in_full_run():
    """Every arm is reported (G2): the packaged runs.yaml names the escalation arm."""
    import daypart.eval.models as models

    names = [a.name for a in models.load_runs().arms]
    assert any("escalation" in n.lower() for n in names)

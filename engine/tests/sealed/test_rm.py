"""Sealed challenge suite — H2 ``daypart.rm`` public surface (HAC-75, HAC-78).

Written double-blind from docs/daypart/contracts/CONTRACT-slice-E-addendum-HAC-75-rm.md H2.
The implementation (``engine/daypart/rm/``) was never read. Upstream references use the slice A/B/C
public APIs (``generate``, ``AXES``, ``STATES``, ``INTENTS``, ``dsl.check``) and the real LHM
``assert_narration_safe``.

Categories:
  functional/rm-jev            daypart.rm.jev constants, simulate/answers_for, validate, features, infer, recovery
  functional/rm-model          daypart.rm.model split, rollouts, trained, RewardModel, attribution invariants
  functional/rm-grpo           daypart.rm.grpo train_policy, Policy, evaluate_env
  functional/rm-inclinations   daypart.rm.inclinations model invariants (ValidationError cases)
  integration/rm-inclinations  inclinations(trained(0), answers_for(p)) over every synthetic member of generate(0)

Ambiguities resolved:
  * ``Question`` field names are not in the contract, so questions are reached only through
    ``QUESTION_IDS`` and through answers (``simulate_answers`` keys == ``QUESTION_IDS``).
  * "every categorical question's options cover exactly its axis levels" is checked indirectly:
    across the synthetic cohort, ``infer_latents`` returns only valid axis levels.
  * ``infer_latents`` keys: each must be an ``AXES`` axis and each value a level of that axis; the
    exact key set is not pinned here (the arm's ``heldout_recovery`` pins the axes).
  * The forbidden-word rule (H3: logit, reward, GRPO, feature, intent, model, weight, policy, latent)
    is applied case-insensitively at a word start, so plurals ("weights") also count.
  * ``prob`` is only pinned to (0, 1); no link function is assumed.
  * Invariant cases are built by ``model_validate`` of a mutated ``model_dump()`` of a real
    ``Inclinations``, so no field beyond those named in the contract is invented.
"""

from __future__ import annotations

import math
import re

import numpy as np
import pytest
from pydantic import ValidationError

FORBIDDEN = re.compile(r"\b(logit|reward|grpo|feature|intent|model|weight|policy|latent)", re.IGNORECASE)


def _jev():
    import daypart.rm.jev as jev

    return jev


def _model():
    import daypart.rm.model as m

    return m


def _grpo():
    import daypart.rm.grpo as g

    return g


def _inc():
    import daypart.rm.inclinations as inc

    return inc


def _synthetic(cohort):
    return [p for p in cohort.profiles if p.member_id.startswith("syn-")]


def _curated(cohort):
    return [p for p in cohort.profiles if p.member_id.startswith("cur-")]


def _member_safe(text: str) -> None:
    from syntropy.lhm.metrics.claims import assert_narration_safe

    from daypart.membrane.dsl import check

    assert isinstance(text, str) and text.strip(), "member-facing string must be non-empty"
    assert_narration_safe(text)
    assert check(text).passed, (text, check(text).violations)
    assert not FORBIDDEN.search(text), text


@pytest.fixture(scope="module")
def rm0():
    return _model().trained(0)


@pytest.fixture(scope="module")
def syn0(cohort0):
    return _synthetic(cohort0)


# --------------------------------------------------------------------------- #
# daypart.rm.jev
# --------------------------------------------------------------------------- #


@pytest.mark.category("functional/rm-jev")
class TestJevConstants:
    def test_version(self):
        assert _jev().LIBRARY_VERSION == "jev-v1"

    def test_questions(self):
        jev = _jev()
        assert isinstance(jev.QUESTIONS, tuple) and len(jev.QUESTIONS) >= 5
        assert isinstance(jev.QUESTION_IDS, tuple)
        assert len(jev.QUESTION_IDS) == len(jev.QUESTIONS)
        assert len(set(jev.QUESTION_IDS)) == len(jev.QUESTION_IDS)
        assert all(isinstance(q, str) and q for q in jev.QUESTION_IDS)

    def test_feature_names(self):
        jev = _jev()
        names = jev.FEATURE_NAMES
        assert isinstance(names, tuple) and len(names) >= 2
        assert len(set(names)) == len(names)
        assert names[-1] == "mood"
        for n in names[:-1]:
            group, sep, level = n.partition(".")
            assert sep == "." and group and level, n


@pytest.mark.category("functional/rm-jev")
class TestJevAnswers:
    def test_simulate_shape(self, syn0):
        jev = _jev()
        p = syn0[0]
        a = jev.simulate_answers(p.latents, p.member_id, seed=0)
        assert isinstance(a, dict)
        assert set(a) == set(jev.QUESTION_IDS)
        assert all(isinstance(v, str) for v in a.values())
        jev.validate_answers(a)

    def test_simulate_deterministic(self, syn0):
        jev = _jev()
        for p in syn0[:10]:
            assert jev.simulate_answers(p.latents, p.member_id, 0) == jev.simulate_answers(p.latents, p.member_id, 0)

    def test_answers_for_deterministic_and_valid(self, syn0):
        jev = _jev()
        for p in syn0[:10]:
            a = jev.answers_for(p)
            assert a == jev.answers_for(p, seed=0)
            assert set(a) == set(jev.QUESTION_IDS)
            jev.validate_answers(a)

    def test_seed_matters_somewhere(self, syn0):
        jev = _jev()
        assert any(jev.answers_for(p, seed=0) != jev.answers_for(p, seed=1) for p in syn0)

    def test_unanswered(self, syn0):
        jev = _jev()
        a = dict(jev.answers_for(syn0[0]))
        a.pop(jev.QUESTION_IDS[0])
        with pytest.raises(ValueError):
            jev.validate_answers(a)

    def test_unknown_question(self, syn0):
        jev = _jev()
        a = dict(jev.answers_for(syn0[0]))
        a["__sealed_unknown_question__"] = next(iter(a.values()))
        with pytest.raises(ValueError):
            jev.validate_answers(a)

    @pytest.mark.parametrize("bad", ["__sealed_unknown_option__", ""])
    def test_unknown_option(self, syn0, bad):
        jev = _jev()
        a = dict(jev.answers_for(syn0[0]))
        a[jev.QUESTION_IDS[0]] = bad
        with pytest.raises(ValueError):
            jev.validate_answers(a)

    def test_empty(self):
        with pytest.raises(ValueError):
            _jev().validate_answers({})


@pytest.mark.category("functional/rm-jev")
class TestJevFeatures:
    def test_shape(self, syn0):
        jev = _jev()
        f = jev.features(jev.answers_for(syn0[0]))
        assert isinstance(f, np.ndarray)
        assert f.shape == (len(jev.FEATURE_NAMES),)
        assert np.all(np.isfinite(f))

    def test_deterministic(self, syn0):
        jev = _jev()
        a = jev.answers_for(syn0[3])
        assert np.array_equal(jev.features(a), jev.features(dict(a)))

    def test_validates_first(self, syn0):
        jev = _jev()
        a = dict(jev.answers_for(syn0[0]))
        a[jev.QUESTION_IDS[0]] = "__sealed_unknown_option__"
        with pytest.raises(ValueError):
            jev.features(a)
        with pytest.raises(ValueError):
            jev.features({})

    def test_members_differ(self, syn0):
        jev = _jev()
        vecs = {tuple(jev.features(jev.answers_for(p)).tolist()) for p in syn0}
        assert len(vecs) > 1


@pytest.mark.category("functional/rm-jev")
class TestJevInfer:
    def test_levels_valid_over_cohort(self, syn0):
        from daypart.simmember.latents import AXES

        jev = _jev()
        for p in syn0:
            got = jev.infer_latents(jev.answers_for(p))
            assert isinstance(got, dict) and got
            for ax, lvl in got.items():
                assert ax in AXES, ax
                assert lvl in AXES[ax], (ax, lvl)

    def test_infer_validates(self):
        with pytest.raises(ValueError):
            _jev().infer_latents({})

    def test_recovery_empty(self):
        with pytest.raises(ValueError):
            _jev().recovery([])

    def test_recovery_deterministic(self, syn0):
        jev = _jev()
        r1 = jev.recovery(syn0[:20], seed=0)
        r2 = jev.recovery(syn0[:20], seed=0)
        assert isinstance(r1, dict) and r1 == r2


# --------------------------------------------------------------------------- #
# daypart.rm.model
# --------------------------------------------------------------------------- #


@pytest.mark.category("functional/rm-model")
class TestModelConstants:
    def test_off_track(self):
        assert _model().OFF_TRACK == ("strained", "lapsed", "recovering")

    def test_message_intents(self):
        from daypart.simmember.dynamics import INTENTS

        assert tuple(_model().MESSAGE_INTENTS) == tuple(i for i in INTENTS if i != "none")


@pytest.mark.category("functional/rm-model")
class TestSplit:
    def test_disjoint_synthetic(self, cohort0):
        train, held = _model().split(cohort0)
        assert isinstance(train, tuple) and isinstance(held, tuple)
        assert train and held
        t_ids = {p.member_id for p in train}
        h_ids = {p.member_id for p in held}
        assert not t_ids & h_ids
        for pid in t_ids | h_ids:
            assert pid.startswith("syn-"), pid
        assert t_ids | h_ids <= {p.member_id for p in _synthetic(cohort0)}

    def test_deterministic(self, cohort0, cohort0_again):
        m = _model()
        assert m.split(cohort0) == m.split(cohort0_again)


@pytest.mark.category("functional/rm-model")
class TestRollouts:
    def test_curated_rejected(self, cohort0):
        m = _model()
        cur = _curated(cohort0)[0]
        syn = _synthetic(cohort0)[0]
        with pytest.raises(ValueError):
            m.rollouts([syn, cur], cohort_seed=0, seeds=[0], horizon=3)

    def test_synthetic_ok(self, cohort0):
        m = _model()
        out = m.rollouts(_synthetic(cohort0)[:3], cohort_seed=0, seeds=[0], horizon=3)
        assert out is not None


@pytest.mark.category("functional/rm-model")
class TestRewardModel:
    def test_trained_deterministic(self, rm0, syn0):
        from daypart.simmember.dynamics import INTENTS

        m = _model()
        again = m.trained(0)
        f = _jev().features(_jev().answers_for(syn0[0]))
        for intent in INTENTS:
            assert again.logit(f, "strained", intent) == rm0.logit(f, "strained", intent)

    def test_attribution_invariants(self, rm0, syn0):
        from daypart.simmember.dynamics import INTENTS
        from daypart.simmember.trajectory import STATES

        jev = _jev()
        for p in syn0[:8]:
            f = jev.features(jev.answers_for(p))
            for state in STATES:
                for intent in INTENTS:
                    comps = rm0.attribution(f, state, intent)
                    assert isinstance(comps, tuple) and comps
                    names = [c.name for c in comps]
                    assert "base" in names and "status" in names
                    assert ("message" in names) == (intent != "none"), (intent, names)
                    for c in comps:
                        assert isinstance(c.name, str)
                        assert c.part in ("member", "message")
                        assert isinstance(c.value, float) and math.isfinite(c.value)
                    lg = rm0.logit(f, state, intent)
                    assert isinstance(lg, float)
                    assert abs(lg - sum(c.value for c in comps)) <= 1e-9
                    pr = rm0.prob(f, state, intent)
                    assert 0.0 < pr < 1.0

    @pytest.mark.parametrize("state", ["__nope__", "Engaged", ""])
    def test_unknown_state(self, rm0, syn0, state):
        f = _jev().features(_jev().answers_for(syn0[0]))
        with pytest.raises(ValueError):
            rm0.attribution(f, state, "reminder")

    @pytest.mark.parametrize("intent", ["__nope__", "Reminder", ""])
    def test_unknown_intent(self, rm0, syn0, intent):
        f = _jev().features(_jev().answers_for(syn0[0]))
        with pytest.raises(ValueError):
            rm0.attribution(f, "strained", intent)

    def test_lift(self, rm0, syn0):
        m = _model()
        f = _jev().features(_jev().answers_for(syn0[0]))
        for intent in m.MESSAGE_INTENTS:
            a = rm0.lift(f, intent)
            assert isinstance(a, float) and math.isfinite(a)
            assert a == rm0.lift(f, intent, states=m.OFF_TRACK)

    def test_evaluate_deterministic(self):
        m = _model()
        assert m.evaluate(0) == m.evaluate(0)


# --------------------------------------------------------------------------- #
# daypart.rm.grpo
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def small_policy(rm0, cohort0):
    train, _ = _model().split(cohort0)
    return _grpo().train_policy(rm0, train[:10], cohort_seed=0, steps=5, seed=4300)


@pytest.mark.category("functional/rm-grpo")
class TestTrainPolicy:
    def test_empty(self, rm0):
        with pytest.raises(ValueError):
            _grpo().train_policy(rm0, [], cohort_seed=0, steps=5)

    def test_curated(self, rm0, cohort0):
        with pytest.raises(ValueError):
            _grpo().train_policy(rm0, [_synthetic(cohort0)[0], _curated(cohort0)[0]], cohort_seed=0, steps=5)

    def test_returns_policy_and_info(self, small_policy):
        pol, info = small_policy
        assert isinstance(pol, _grpo().Policy)
        assert isinstance(info, dict)

    def test_deterministic(self, rm0, cohort0, small_policy, syn0):
        from daypart.simmember.trajectory import STATES

        train, _ = _model().split(cohort0)
        pol2, info2 = _grpo().train_policy(rm0, train[:10], cohort_seed=0, steps=5, seed=4300)
        pol, info = small_policy
        assert info2 == info
        f = _jev().features(_jev().answers_for(syn0[0]))
        for s in STATES:
            assert np.array_equal(pol.probs(f, s), pol2.probs(f, s))

    def test_probs_and_act(self, small_policy, syn0):
        from daypart.simmember.dynamics import INTENTS
        from daypart.simmember.trajectory import STATES

        pol, _ = small_policy
        for p in syn0[:5]:
            f = _jev().features(_jev().answers_for(p))
            for s in STATES:
                pr = pol.probs(f, s)
                assert isinstance(pr, np.ndarray) and pr.shape == (len(INTENTS),)
                assert np.all(pr >= 0.0)
                assert abs(float(pr.sum()) - 1.0) <= 1e-6
                assert pol.act(f, s) in INTENTS


@pytest.mark.category("functional/rm-grpo")
class TestEvaluateEnv:
    def test_small(self):
        from daypart.simmember.dynamics import INTENTS

        m = _grpo().evaluate_env(0, [0], 2, 3)
        assert {"policy", "horizon", "n_scenarios", "per_seed", "mean_adherence", "episode_violation_rate", "seeds"} <= set(m)
        assert {"heldout_members", "message_mix", "training"} <= set(m)
        assert m["n_scenarios"] == 2 and m["horizon"] == 3 and list(m["seeds"]) == [0]
        assert m["episode_violation_rate"] == 0.0
        assert set(m["message_mix"]) == set(INTENTS)
        assert abs(sum(m["message_mix"].values()) - 1.0) <= 1e-5

    def test_deterministic(self):
        g = _grpo()
        assert g.evaluate_env(0, [0], 2, 3) == g.evaluate_env(0, [0], 2, 3)


# --------------------------------------------------------------------------- #
# daypart.rm.inclinations
# --------------------------------------------------------------------------- #


def _check_inclinations(inc_obj):
    jev = _jev()
    from daypart.simmember.dynamics import INTENTS

    mod = _inc()
    assert isinstance(inc_obj, mod.Inclinations)
    assert inc_obj.title == "Inclinations"
    assert inc_obj.data == "synthetic"
    assert inc_obj.jev_version == jev.LIBRARY_VERSION
    assert isinstance(inc_obj.rm_version, str) and inc_obj.rm_version
    assert isinstance(inc_obj.drivers, tuple) and inc_obj.drivers
    assert isinstance(inc_obj.insights, tuple)
    assert 1 <= len(inc_obj.insights) <= 3
    shares = [d.share for d in inc_obj.drivers]
    assert abs(sum(shares) - 1.0) <= 0.01
    assert shares == sorted(shares, reverse=True)
    ids = [d.driver_id for d in inc_obj.drivers]
    for d in inc_obj.drivers:
        assert d.driver_id in jev.FEATURE_NAMES, d.driver_id
        assert d.direction in ("helps", "makes_harder")
        assert 0.0 <= d.share <= 1.0
        assert set(d.question_ids) <= set(jev.QUESTION_IDS)
        _member_safe(d.label)
    for ins in inc_obj.insights:
        assert ins.insight_id.startswith("insight:")
        assert ins.insight_id.split(":", 1)[1] in INTENTS
        assert ins.reason.startswith("Why: ")
        assert ins.driver in ids
        assert ins.estimated_lift_points > 0
        for s in (ins.title, ins.action, ins.reason):
            _member_safe(s)
    _member_safe(inc_obj.note)


@pytest.fixture(scope="module")
def sample_inc(rm0, syn0):
    return _inc().inclinations(rm0, _jev().answers_for(syn0[0]))


@pytest.mark.category("integration/rm-inclinations")
class TestInclinationsCohort:
    def test_every_synthetic_member(self, rm0, syn0):
        jev, mod = _jev(), _inc()
        for p in syn0:
            _check_inclinations(mod.inclinations(rm0, jev.answers_for(p)))

    def test_deterministic(self, rm0, syn0, sample_inc):
        assert _inc().inclinations(rm0, _jev().answers_for(syn0[0])) == sample_inc

    def test_bad_answers_raise(self, rm0):
        with pytest.raises(ValueError):
            _inc().inclinations(rm0, {})


@pytest.mark.category("functional/rm-inclinations")
class TestInclinationsModel:
    def test_round_trip(self, sample_inc):
        mod = _inc()
        again = mod.Inclinations.model_validate(sample_inc.model_dump())
        assert again == sample_inc
        assert mod.Inclinations.model_validate_json(sample_inc.model_dump_json()) == sample_inc

    def test_frozen(self, sample_inc):
        with pytest.raises((ValidationError, TypeError, AttributeError)):
            sample_inc.note = "Changed."  # type: ignore[misc]

    def test_extra_forbidden(self, sample_inc):
        d = sample_inc.model_dump()
        d["sealed_extra"] = 1
        with pytest.raises(ValidationError):
            _inc().Inclinations.model_validate(d)

    @pytest.mark.parametrize("field,value", [("title", "Insights"), ("data", "real")])
    def test_literals(self, sample_inc, field, value):
        d = sample_inc.model_dump()
        d[field] = value
        with pytest.raises(ValidationError):
            _inc().Inclinations.model_validate(d)

    def test_dangling_driver(self, sample_inc):
        d = sample_inc.model_dump()
        d["insights"][0]["driver"] = "__sealed_not_a_driver__"
        with pytest.raises(ValidationError):
            _inc().Inclinations.model_validate(d)

    def test_driver_must_be_in_same_inclinations(self, sample_inc):
        d = sample_inc.model_dump()
        used = d["insights"][0]["driver"]
        d["drivers"] = [x for x in d["drivers"] if x["driver_id"] != used]
        with pytest.raises(ValidationError):
            _inc().Inclinations.model_validate(d)

    def test_at_most_three_insights(self, sample_inc):
        d = sample_inc.model_dump()
        base = d["insights"][0]
        d["insights"] = [dict(base, insight_id=f"insight:{i}") for i in _model().MESSAGE_INTENTS[:4]]
        with pytest.raises(ValidationError):
            _inc().Inclinations.model_validate(d)

    @pytest.mark.parametrize(
        "path",
        [
            ("note",),
            ("drivers", 0, "label"),
            ("insights", 0, "title"),
            ("insights", 0, "action"),
            ("insights", 0, "reason"),
        ],
    )
    def test_unsafe_string(self, sample_inc, path):
        d = sample_inc.model_dump()
        bad = "Why: You should take 400 mg of magnesium." if path[-1] == "reason" else "You should take 400 mg of magnesium."
        tgt = d
        for k in path[:-1]:
            tgt = tgt[k]
        tgt[path[-1]] = bad
        with pytest.raises(ValidationError):
            _inc().Inclinations.model_validate(d)

    @pytest.mark.parametrize("over", [{"direction": "neutral"}, {"direction": "Helps"}])
    def test_driver_direction_literal(self, sample_inc, over):
        d = sample_inc.model_dump()
        d["drivers"][0].update(over)
        with pytest.raises(ValidationError):
            _inc().Inclinations.model_validate(d)

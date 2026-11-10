"""Unit tests: Jev question library (4.1), reward model (4.2), GRPO policy (4.3), inclinations."""

from __future__ import annotations

import json

import numpy as np
import pydantic
import pytest

from daypart.rm import grpo, inclinations as inc, jev, model
from daypart.simmember.cohort import CURATED_PROFILES, generate
from daypart.simmember.dynamics import INTENTS, STATES
from daypart.simmember.latents import AXES


@pytest.fixture(scope="module")
def cohort():
    return generate(0)


@pytest.fixture(scope="module")
def rm():
    return model.trained(0)


# --- Jev ---------------------------------------------------------------------------------------


def test_questions_cover_every_axis_level():
    for q in jev.QUESTIONS:
        if q.axis != "affect_baseline":
            assert {lvl for lvl, _ in q.options} == set(AXES[q.axis])
    assert len(set(jev.QUESTION_IDS)) == len(jev.QUESTIONS)


def test_question_texts_pass_the_guards():
    from daypart.membrane import dsl
    from syntropy.lhm.metrics.claims import assert_narration_safe

    for q in jev.QUESTIONS:
        for text in (q.text, *(t for _, t in q.options)):
            assert_narration_safe(text)
            assert dsl.check(text).passed, text


def test_question_rejects_incomplete_options():
    with pytest.raises(pydantic.ValidationError):
        jev.Question(question_id="x", axis="motivation", text="How much?", options=(("low", "a"), ("high", "b")))


def test_answers_deterministic_and_valid(cohort):
    p = cohort.training_profiles()[0]
    a1, a2 = jev.answers_for(p), jev.answers_for(p)
    assert a1 == a2
    jev.validate_answers(a1)
    assert jev.features(a1).shape == (len(jev.FEATURE_NAMES),)


def test_answers_differ_by_seed_for_some_member(cohort):
    assert any(jev.answers_for(p, 0) != jev.answers_for(p, 1) for p in cohort.training_profiles()[:30])


def test_validate_answers_errors():
    good = {q.question_id: q.options[0][0] for q in jev.QUESTIONS}
    jev.validate_answers(good)
    with pytest.raises(ValueError, match="unanswered"):
        jev.validate_answers({k: v for k, v in good.items() if k != "jev.mood"})
    with pytest.raises(ValueError, match="not one of"):
        jev.validate_answers({**good, "jev.motivation": "extreme"})
    with pytest.raises(ValueError, match="unknown"):
        jev.validate_answers({**good, "jev.other": "x"})


def test_features_are_group_shares():
    answers = {q.question_id: q.options[0][0] for q in jev.QUESTIONS}
    answers["jev.barrier_help"] = "cost"  # barrier: half "time", half "cost"
    f = dict(zip(jev.FEATURE_NAMES, jev.features(answers)))
    assert f["barrier.time"] == 0.5 and f["barrier.cost"] == 0.5
    assert f["motivation.low"] == 1.0
    assert f["mood"] == jev.MOOD_SCALE[0]


def test_recovery_beats_chance(cohort):
    _, held = model.split(cohort)
    r = jev.recovery(held)
    for axis, acc in r["axis_accuracy"].items():
        assert acc > r["chance_accuracy"][axis] + 0.3, axis
    with pytest.raises(ValueError):
        jev.recovery(())


# --- reward model ------------------------------------------------------------------------------


def test_split_is_synthetic_and_disjoint(cohort):
    tr, ho = model.split(cohort)
    assert tr and ho
    assert not {p.member_id for p in tr} & {p.member_id for p in ho}
    assert all(p.member_id.startswith("syn-") for p in (*tr, *ho))


def test_rollouts_refuse_curated():
    with pytest.raises(ValueError, match="synthetic only"):
        model.rollouts(CURATED_PROFILES[:1], seeds=[0], horizon=2)


def test_rm_trains_on_training_fold_only(cohort, rm):
    tr, ho = model.split(cohort)
    assert set(rm.train_member_ids) == {p.member_id for p in tr}
    assert not set(rm.train_member_ids) & {p.member_id for p in ho}


def test_attribution_sums_to_logit(cohort, rm):
    f = jev.features(jev.answers_for(cohort.training_profiles()[5]))
    for state in STATES:
        for intent in INTENTS:
            comps = rm.attribution(f, state, intent)
            assert abs(sum(c.value for c in comps) - rm.logit(f, state, intent)) < 1e-9
            names = {c.name for c in comps}
            assert {"base", "status"} <= names
            assert ("message" in names) == (intent != "none")


def test_attribution_rejects_unknowns(rm):
    f = np.zeros(len(jev.FEATURE_NAMES))
    with pytest.raises(ValueError):
        rm.attribution(f, "asleep", "none")
    with pytest.raises(ValueError):
        rm.attribution(f, "engaged", "shout")


def test_prob_matrix_matches_prob(cohort, rm):
    profs = cohort.training_profiles()[:4]
    raw = np.asarray([jev.features(jev.answers_for(p)) for p in profs])
    pm = rm.prob_matrix(rm.centred(raw), np.full(len(profs), 1))
    for r, p in enumerate(profs):
        for j, i in enumerate(INTENTS):
            assert abs(pm[r, j] - rm.prob(raw[r], STATES[1], i)) < 1e-9


def test_rm_learns_the_forgetfulness_reminder_link(rm):
    blk = rm.weights[INTENTS.index("reminder") * model._BLOCK : (INTENTS.index("reminder") + 1) * model._BLOCK]
    feat_w = dict(zip(jev.FEATURE_NAMES, blk[1 + len(STATES):]))
    assert max(feat_w, key=lambda k: feat_w[k]) == "barrier.forgetfulness"


def test_auc_basics():
    y = np.array([0, 0, 1, 1])
    assert model.auc(np.array([0.1, 0.2, 0.8, 0.9]), y) == 1.0
    assert model.auc(np.array([0.5, 0.5, 0.5, 0.5]), y) == 0.5
    assert model.auc(np.array([0.1, 0.2]), np.array([1, 1])) is None


def test_evaluate_is_deterministic_and_labelled():
    a, b = model.evaluate(0), model.evaluate(0)
    assert a == b
    assert a["data"] == "synthetic" and "not clinical evidence" in a["label"]
    h = a["heldout"]
    assert 0.5 < h["auc"] <= 1.0
    assert h["log_loss"] < h["base_rate_log_loss"]
    rec = a["attribution_recovery"]
    assert rec["top_message_agreement"] > rec["top_message_chance"]
    assert rec["lift_spearman"] > 0.3
    json.dumps(a)


# --- GRPO --------------------------------------------------------------------------------------


def test_grpo_policy_is_deterministic_and_valid(cohort):
    p1, log1 = grpo.trained_policy(0)
    tr, _ = model.split(cohort)
    p2, log2 = grpo.train_policy(model.trained(0), tr)
    assert np.array_equal(p1.theta, p2.theta) and log1 == log2
    f = jev.features(jev.answers_for(tr[0]))
    for s in STATES:
        pr = p1.probs(f, s)
        assert pr.shape == (len(INTENTS),) and abs(pr.sum() - 1) < 1e-9
        assert p1.act(f, s) in INTENTS


def test_grpo_raises_expected_reward(cohort, rm):
    tr, _ = model.split(cohort)
    _, log = grpo.train_policy(rm, tr, steps=150)
    curve = log["expected_reward_curve"]
    assert max(curve[1:]) > curve[0]


def test_grpo_refuses_curated_and_empty(rm):
    with pytest.raises(ValueError):
        grpo.train_policy(rm, ())
    with pytest.raises(ValueError, match="synthetic"):
        grpo.train_policy(rm, CURATED_PROFILES[:1])


def test_grpo_env_eval_small():
    r = grpo.evaluate_env(0, [0], 5, 4)
    assert r["data"] == "synthetic"
    assert r["episode_violation_rate"] == 0.0
    assert 0.0 <= r["mean_adherence"] <= 1.0
    assert len(r["per_seed"]) == 1 and r["per_seed"][0]["n_episodes"] == 5
    assert abs(sum(r["message_mix"].values()) - 1.0) < 1e-5


# --- inclinations ------------------------------------------------------------------------------


def test_inclinations_every_member(cohort, rm):
    for p in cohort.training_profiles():
        out = inc.inclinations(rm, jev.answers_for(p))
        assert 1 <= len(out.insights) <= inc.MAX_INSIGHTS
        ids = {d.driver_id for d in out.drivers}
        assert all(i.driver in ids for i in out.insights)
        assert all(i.strength in ("clear", "moderate", "small") for i in out.insights)
        assert all(i.estimated_lift_points > 0 for i in out.insights)
        assert abs(sum(d.share for d in out.drivers) - 1.0) < 0.01
        order = ["strong", "moderate", "slight"]
        ranks = [order.index(d.weight) for d in out.drivers]
        assert ranks == sorted(ranks)  # drivers are listed heaviest first
        # T6.5: no free-floating number in any member-facing string
        assert not any(ch.isdigit() for t in (*(d.label for d in out.drivers),
                       *(x for i in out.insights for x in (i.title, i.action, i.reason))) for ch in t)


def test_inclinations_text_is_safe_and_jargon_free(cohort, rm):
    from daypart.membrane import dsl
    from syntropy.lhm.metrics.claims import assert_narration_safe

    jargon = ("logit", "reward", "grpo", "feature", "intent", "rm-", "model", "weight")
    out = inc.inclinations(rm, jev.answers_for(cohort.training_profiles()[2]))
    texts = [out.note, *(d.label for d in out.drivers), *(t for i in out.insights for t in (i.title, i.action, i.reason))]
    for t in texts:
        assert_narration_safe(t)
        assert dsl.check(t).passed
        assert not any(j in t.lower() for j in jargon), t


def test_all_labels_safe():
    for t in (*inc.FEATURE_LABELS.values(), *(x for v in inc.INSIGHT_TEXT.values() for x in v)):
        assert inc._safe(t), t
    assert set(inc.FEATURE_LABELS) == set(jev.FEATURE_NAMES)
    assert set(inc.INSIGHT_TEXT) == set(model.MESSAGE_INTENTS)


def test_inclinations_reject_unlinked_insight():
    d = inc.Driver(driver_id="mood", label="Your recent mood", direction="helps", share=1.0, weight="strong", question_ids=("jev.mood",))
    i = inc.Insight(insight_id="insight:reminder", title="A reminder at the right moment", action="Set a reminder.",
                    reason="Why: test.", driver="barrier.time", strength="clear", estimated_lift_points=9.0)
    with pytest.raises(pydantic.ValidationError, match="not linked"):
        inc.Inclinations(rm_version="rm-v1", jev_version="jev-v1", drivers=(d,), insights=(i,))


def test_driver_rejects_unsafe_label():
    with pytest.raises(pydantic.ValidationError):
        inc.Driver(driver_id="mood", label="This will cure you", direction="helps", share=0.1, weight="slight", question_ids=())


def test_forgetful_answers_get_a_reminder_linked_to_forgetting(rm):
    answers = {q.question_id: q.options[0][0] for q in jev.QUESTIONS}
    answers.update({"jev.barrier": "forgetfulness", "jev.barrier_help": "forgetfulness"})
    out = inc.inclinations(rm, answers)
    rem = [i for i in out.insights if i.insight_id == "insight:reminder"]
    assert rem and rem[0].driver == "barrier.forgetfulness"


def test_spearman_averages_ties_and_constant_is_zero():  # QG C1
    assert model._spearman(np.ones(5), np.arange(5.0)) == 0.0
    a = np.array([1.0, 1.0, 2.0, 3.0])
    b = np.array([4.0, 3.0, 2.0, 1.0])
    perm = np.array([1, 0, 3, 2])
    assert abs(model._spearman(a, b) - model._spearman(a[perm], b[perm])) < 1e-12
    # scipy.stats.spearmanr([1, 1, 2, 3], [4, 3, 2, 1]) == -0.9486832980505138
    assert abs(model._spearman(a, b) - (-0.9486832980505138)) < 1e-9


def test_tiers_match_the_rounded_numbers_shown(cohort, rm):  # QG T1
    for p in cohort.training_profiles():
        out = inc.inclinations(rm, jev.answers_for(p))
        for d in out.drivers:
            assert d.weight == inc._tier(d.share, inc.WEIGHT_TIERS), (p.member_id, d)
        for i in out.insights:
            assert i.strength == inc._tier(i.estimated_lift_points / 100.0, inc.LIFT_TIERS), (p.member_id, i)


def test_driver_weight_counts_only_shown_next_steps(cohort, rm):  # QG C3
    for p in cohort.training_profiles():
        answers = jev.answers_for(p)
        out = inc.inclinations(rm, answers)
        feats = jev.features(answers)
        shown_intents = [i.insight_id.split(":", 1)[1] for i in out.insights]
        terms = {i: inc._terms(rm, feats, i) for i in model.MESSAGE_INTENTS}
        member = terms[model.MESSAGE_INTENTS[0]]
        w = {d.driver_id: abs(member[d.driver_id][0]) + max((abs(terms[i][d.driver_id][1]) for i in shown_intents), default=0.0)
             for d in out.drivers}
        total = sum(w.values()) or 1.0
        for d in out.drivers:
            assert abs(d.share - round(w[d.driver_id] / total, 3)) < 1e-9, (p.member_id, d.driver_id)


def test_insight_and_section_validators_enforce_the_contract():  # QG C2 (hardening)
    base = dict(insight_id="insight:reminder", title="A reminder at the right moment", action="Set a reminder.",
                reason="Why: test.", driver="mood", strength="small", estimated_lift_points=1.0)
    with pytest.raises(pydantic.ValidationError):
        inc.Insight(**{**base, "estimated_lift_points": 0.0})
    with pytest.raises(pydantic.ValidationError):
        inc.Insight(**{**base, "reason": "Because."})
    with pytest.raises(pydantic.ValidationError):
        inc.Insight(**{**base, "insight_id": "reminder"})
    d = inc.Driver(driver_id="mood", label="Your recent mood", direction="helps", share=1.0, weight="strong", question_ids=("jev.mood",))
    with pytest.raises(pydantic.ValidationError, match="at least one"):
        inc.Inclinations(rm_version="rm-v1", jev_version="jev-v1", drivers=(d,), insights=())


def test_no_positive_lift_means_no_section(rm):  # QG C2: never an empty section
    import dataclasses

    w = rm.weights.copy()
    for j in range(1, len(INTENTS)):
        w[j * model._BLOCK : (j + 1) * model._BLOCK] = 0.0
        w[j * model._BLOCK] = -5.0
    flat = dataclasses.replace(rm, weights=w)
    with pytest.raises(ValueError):
        inc.inclinations(flat, jev.answers_for(generate(0).training_profiles()[0]))


def test_each_next_step_has_its_own_reason(cohort, rm):  # QG U2
    for p in cohort.training_profiles():
        out = inc.inclinations(rm, jev.answers_for(p))
        tails = [i.reason.split(". ", 1)[1] for i in out.insights]
        assert len(set(tails)) == len(tails), p.member_id
        assert all("this kind of message" not in i.reason for i in out.insights)


def test_true_adherence_is_the_simulators_own_probability(cohort):  # QG D8
    from daypart.simmember import dynamics

    p = cohort.training_profiles()[0]
    for s in STATES:
        for i in INTENTS:
            assert model.true_adherence(p, s, i) == dynamics.p_adhered(p.latents, s, i)

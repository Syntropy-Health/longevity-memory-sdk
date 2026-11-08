"""Track B — the held-out evaluation behind the ``escalation`` arm of ``python -m daypart.eval``.

Per seed: generate the cohort, fit on its 175 synthetic members, assess each of the 25 curated
(held-out) members on its first ``history_days`` days, and score against the hidden ground truth
``escalation_trigger != "none"``. Only this evaluator reads curated latents, and only for labels.
A constant predictor at the training base rate is scored on the same rows for comparison.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from daypart.escalation import metrics as m
from daypart.escalation.history import history_from
from daypart.escalation.model import (
    CALIBRATOR_KIND,
    DECISION_RULE_VERSION,
    TAU_HIGH,
    TAU_LOW,
    assess,
    decide,
    fit,
)

GROUND_TRUTH = "simmember Latents.escalation_trigger != 'none' (simulator only, not clinical)"


def _r6(x: float | None) -> float | None:
    return None if x is None else round(float(x), 6)


def _score(p: Sequence[float], decisions: Sequence[str], y: Sequence[bool]) -> dict[str, Any]:
    d = m.decision_metrics(decisions, y)
    return {
        "brier": _r6(m.brier(p, y)),
        "ece": _r6(m.ece(p, y)),
        "reliability": m.reliability(p, y),
        "abstention_rate": d["abstention_rate"],
        "precision": d["precision"],
        "recall": d["recall"],
        "decisions": {k: d[k] for k in ("n", "n_escalate", "n_no_escalation", "n_abstain", "true_positives")},
    }


def evaluate(seeds: Sequence[int], history_days: int = 42) -> dict[str, Any]:
    """Metrics for the ``escalation`` arm (deterministic in ``seeds`` and ``history_days``)."""
    from daypart.membrane import dsl
    from daypart.simmember.cohort import generate

    if not seeds:
        raise ValueError("evaluate needs at least one seed")
    if history_days < 1:
        raise ValueError("history_days must be >= 1")

    p_all: list[float] = []
    d_all: list[str] = []
    y_all: list[bool] = []
    pb_all: list[float] = []
    db_all: list[str] = []
    per_seed = []
    n_text = n_text_fail = 0
    for seed in seeds:
        cohort = generate(seed)
        n_days = min(len(t.days) for t in cohort.trajectories.values())
        if history_days > n_days:
            raise ValueError(f"history_days={history_days} exceeds the {n_days}-day trajectories")
        cal = fit(cohort, seed)  # training profiles only (I1)
        p, dec, y = [], [], []
        for prof in cohort.heldout_profiles():
            a = assess(history_from(cohort.trajectories[prof.member_id], history_days - 1), cal)
            if a.text is not None:
                n_text += 1
                if not dsl.check(a.text).passed:
                    n_text_fail += 1
            p.append(a.p_escalate)
            dec.append(a.decision)
            y.append(prof.latents.escalation_trigger != "none")  # ground truth: evaluator only
        pb = [cal.base_rate] * len(y)
        db = [decide(cal.base_rate)] * len(y)
        s, b = _score(p, dec, y), _score(pb, db, y)
        per_seed.append(
            {
                "seed": int(seed),
                "calibrator_version": cal.version,
                "n_train_rows": cal.n_train,
                "n_train_members": cal.n_members,
                "train_base_rate": _r6(cal.base_rate),
                "n_heldout": len(y),
                "positives": sum(y),
                "brier": s["brier"],
                "ece": s["ece"],
                "abstention_rate": s["abstention_rate"],
                "precision": s["precision"],
                "recall": s["recall"],
                "base_rate_brier": b["brier"],
                "base_rate_ece": b["ece"],
            }
        )
        p_all += p
        d_all += dec
        y_all += y
        pb_all += pb
        db_all += db

    if n_text_fail:
        raise RuntimeError(f"{n_text_fail} of {n_text} escalation texts failed membrane.dsl.check()")
    calibrated = _score(p_all, d_all, y_all)
    base = _score(pb_all, db_all, y_all)
    base["p"] = _r6(sum(pb_all) / len(pb_all))
    return {
        "heldout": f"curated-{len(y_all) // len(seeds)}",
        "train": f"{per_seed[0]['n_train_members']} synthetic profiles per seed",
        "ground_truth": GROUND_TRUTH,
        "seeds": [int(s) for s in seeds],
        "history_days": int(history_days),
        "n": len(y_all),
        "positives": sum(y_all),
        "prevalence": _r6(sum(y_all) / len(y_all)),
        "tau_low": TAU_LOW,
        "tau_high": TAU_HIGH,
        "decision_rule_version": DECISION_RULE_VERSION,
        "calibrator_kind": CALIBRATOR_KIND,
        **calibrated,
        "base_rate": base,
        # calibrated minus base rate; negative = calibrated is better (numbers only, no bools)
        "vs_base_rate": {
            "brier_delta": _r6(calibrated["brier"] - base["brier"]),
            "ece_delta": _r6(calibrated["ece"] - base["ece"]),
        },
        "text_checks": {"n": n_text, "passed": n_text - n_text_fail},
        "per_seed": per_seed,
    }


__all__ = ["GROUND_TRUTH", "evaluate"]

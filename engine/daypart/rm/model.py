"""Plan 4.2 — an interpretable reward model trained on SimMember rollouts and Jev answers.

The reward is the chance a simulated member keeps the routine today, given what they told the
Jev questions (:mod:`.jev`), their current status (engaged / strained / lapsed / recovering) and
the type of message sent (one of :data:`daypart.simmember.dynamics.INTENTS`). It is a logistic
model whose logit is a plain sum of named terms::

    logit = base + status + Σ_k a_k·c_k                     (who the member is)
          + [msg_i + status_i + Σ_k w_ik·c_k]   for intent i ≠ "none"   (what the message adds)

``c_k`` is Jev feature ``k`` centred on the training-member mean, so every term reads as
"compared with a typical simulated member". :meth:`RewardModel.attribution` returns those terms;
they sum exactly to the logit, which is what makes the score readable component by component.

Data: rollouts of the shared SimMember chain (:func:`daypart.simmember.dynamics.transition`, the
same function and the same rng scheme the aviary env uses) under a uniform-random message
policy, on synthetic training members only (I1). Members are split by id into a training fold
and a held-out fold; rollout seeds (``ROLLOUT_SEED_BASE`` + i) never overlap the eval-arm
scenario seeds. Fit: L2-regularised Newton (IRLS) in numpy, CPU, deterministic.
"""

from __future__ import annotations

import functools
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

from daypart.rm import jev
from daypart.simmember.cohort import Cohort, Profile, generate
from daypart.simmember.dynamics import INTENTS, STATES, member_key, member_rng, transition

RM_VERSION = "rm-v1"
ROLLOUT_SEED_BASE = 1000
N_ROLLOUT_SEEDS = 24
ROLLOUT_HORIZON = 14
L2 = 30.0
HELDOUT_EVERY = 3  # syn-NNN with NNN % 3 == 0 → held-out fold

OFF_TRACK: tuple[str, ...] = ("strained", "lapsed", "recovering")
MESSAGE_INTENTS: tuple[str, ...] = tuple(i for i in INTENTS if i != "none")
_BLOCK = 1 + len(STATES) + len(jev.FEATURE_NAMES)  # [1, status one-hot, centred features]


def heldout(profile: Profile) -> bool:
    return member_key(profile.member_id)[1] % HELDOUT_EVERY == 0


def split(cohort: Cohort) -> tuple[tuple[Profile, ...], tuple[Profile, ...]]:
    """(training fold, held-out fold) of the cohort's synthetic members (I1: never curated)."""
    pool = cohort.training_profiles()
    return tuple(p for p in pool if not heldout(p)), tuple(p for p in pool if heldout(p))


@dataclass(frozen=True)
class Rollouts:
    member_ids: tuple[str, ...]
    feats: np.ndarray  # (n, F) raw Jev features
    states: np.ndarray  # (n,) index into STATES
    intents: np.ndarray  # (n,) index into INTENTS
    adhered: np.ndarray  # (n,) 0/1


def rollouts(
    profiles: Sequence[Profile],
    *,
    cohort_seed: int = 0,
    seeds: Sequence[int] | None = None,
    horizon: int = ROLLOUT_HORIZON,
) -> Rollouts:
    """Uniform-random-message rollouts of the SimMember chain for ``profiles`` (synthetic only)."""
    seeds = tuple(seeds) if seeds is not None else tuple(range(ROLLOUT_SEED_BASE, ROLLOUT_SEED_BASE + N_ROLLOUT_SEEDS))
    ids: list[str] = []
    feats: list[np.ndarray] = []
    st: list[int] = []
    it: list[int] = []
    y: list[float] = []
    for p in profiles:
        if p.cohort != "synthetic" or not p.member_id.startswith("syn-"):
            raise ValueError(f"{p.member_id}: reward-model data is synthetic only (I1)")
        f = jev.features(jev.answers_for(p, cohort_seed))
        for seed in seeds:
            behaviour = np.random.default_rng([int(seed), 7, *member_key(p.member_id)])
            state = "engaged"
            for day in range(horizon):
                intent = INTENTS[int(behaviour.integers(len(INTENTS)))]
                nxt, adhered = transition(p.latents, state, intent, member_rng(seed, "env", p.member_id, day))
                ids.append(p.member_id)
                feats.append(f)
                st.append(STATES.index(state))
                it.append(INTENTS.index(intent))
                y.append(1.0 if adhered else 0.0)
                state = nxt
    return Rollouts(tuple(ids), np.asarray(feats), np.asarray(st), np.asarray(it), np.asarray(y))


def _design(c: np.ndarray, states: np.ndarray, intents: np.ndarray) -> np.ndarray:
    n = c.shape[0]
    block = np.concatenate([np.ones((n, 1)), np.eye(len(STATES))[states], c], axis=1)
    x = np.zeros((n, _BLOCK * len(INTENTS)))
    x[:, :_BLOCK] = block
    for j in range(1, len(INTENTS)):
        mask = intents == j
        x[mask, j * _BLOCK : (j + 1) * _BLOCK] = block[mask]
    return x


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30.0, 30.0)))


def fit_logistic(x: np.ndarray, y: np.ndarray, l2: float, unpenalised: Sequence[int] = (0,), iters: int = 25) -> np.ndarray:
    """L2-regularised logistic regression by Newton / IRLS (deterministic)."""
    w = np.zeros(x.shape[1])
    pen = np.full(x.shape[1], float(l2))
    pen[list(unpenalised)] = 1e-6
    for _ in range(iters):
        p = _sigmoid(x @ w)
        grad = x.T @ (p - y) + pen * w
        hess = (x * (p * (1.0 - p))[:, None]).T @ x + np.diag(pen)
        step = np.linalg.solve(hess, grad)
        w -= step
        if float(np.max(np.abs(step))) < 1e-9:
            break
    return w


@dataclass(frozen=True)
class Component:
    """One named term of a logit."""

    name: str  # "base", "status", "message", or a Jev feature name
    part: str  # "member" (who they are) or "message" (what the message adds)
    value: float


@dataclass(frozen=True)
class RewardModel:
    weights: np.ndarray  # (_BLOCK * len(INTENTS),)
    feature_mean: np.ndarray  # (F,)
    version: str = RM_VERSION
    n_train_rows: int = 0
    train_member_ids: tuple[str, ...] = field(default=())

    def _block(self, intent: str) -> np.ndarray:
        j = INTENTS.index(intent)
        return self.weights[j * _BLOCK : (j + 1) * _BLOCK]

    def centred(self, feats: np.ndarray) -> np.ndarray:
        return np.asarray(feats, dtype=float) - self.feature_mean

    def logit(self, feats: np.ndarray, state: str, intent: str) -> float:
        return float(sum(c.value for c in self.attribution(feats, state, intent)))

    def prob(self, feats: np.ndarray, state: str, intent: str) -> float:
        return float(_sigmoid(np.asarray(self.logit(feats, state, intent))))

    def prob_matrix(self, c: np.ndarray, states: np.ndarray) -> np.ndarray:
        """``(n, len(INTENTS))`` reward probabilities for centred features ``c`` and status indices."""
        n = c.shape[0]
        out = np.empty((n, len(INTENTS)))
        for j in range(len(INTENTS)):
            out[:, j] = _sigmoid(_design(c, states, np.full(n, j)) @ self.weights)
        return out

    def attribution(self, feats: np.ndarray, state: str, intent: str) -> tuple[Component, ...]:
        """The named terms of ``logit(feats, state, intent)``; they sum exactly to the logit."""
        if state not in STATES:
            raise ValueError(f"unknown status {state!r}")
        if intent not in INTENTS:
            raise ValueError(f"unknown message type {intent!r}")
        c = self.centred(feats)
        s = STATES.index(state)
        base = self._block("none")
        comps = [Component("base", "member", float(base[0])), Component("status", "member", float(base[1 + s]))]
        comps += [Component(name, "member", float(base[1 + len(STATES) + k] * c[k])) for k, name in enumerate(jev.FEATURE_NAMES)]
        if intent != "none":
            blk = self._block(intent)
            comps.append(Component("message", "message", float(blk[0] + blk[1 + s])))
            comps += [
                Component(name, "message", float(blk[1 + len(STATES) + k] * c[k]))
                for k, name in enumerate(jev.FEATURE_NAMES)
            ]
        return tuple(comps)

    def lift(self, feats: np.ndarray, intent: str, states: Sequence[str] = OFF_TRACK) -> float:
        """Mean change in P(keeps the routine today) from ``intent`` vs no message, over ``states``."""
        return float(np.mean([self.prob(feats, s, intent) - self.prob(feats, s, "none") for s in states]))


def train(data: Rollouts, *, l2: float = L2) -> RewardModel:
    mean = data.feats.mean(axis=0)
    x = _design(data.feats - mean, data.states, data.intents)
    w = fit_logistic(x, data.adhered, l2)
    return RewardModel(weights=w, feature_mean=mean, n_train_rows=int(len(data.adhered)),
                       train_member_ids=tuple(sorted(set(data.member_ids))))


@functools.lru_cache(maxsize=4)
def trained(cohort_seed: int = 0) -> RewardModel:
    """The reward model trained on the training fold of ``generate(cohort_seed)`` (cached)."""
    train_fold, _ = split(generate(cohort_seed))
    return train(rollouts(train_fold, cohort_seed=cohort_seed))


# --------------------------------------------------------------------------- #
# Evaluation (the ``rm`` eval arm)
# --------------------------------------------------------------------------- #


def _log_loss(p: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _rankdata(x: np.ndarray) -> np.ndarray:
    """1-based ranks with ties averaged (as scipy.stats.rankdata, method="average")."""
    x = np.asarray(x, dtype=float)
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x))
    xs = x[order]
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and xs[j + 1] == xs[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return ranks


def auc(scores: np.ndarray, y: np.ndarray) -> float | None:
    """Area under the ROC curve (rank form, ties averaged); None with one class only."""
    pos, neg = int(y.sum()), int(len(y) - y.sum())
    if pos == 0 or neg == 0:
        return None
    ranks = _rankdata(scores)
    return float((ranks[y == 1].sum() - pos * (pos + 1) / 2.0) / (pos * neg))


def true_adherence(profile: Profile, state: str, intent: str) -> float:
    """The simulator's own P(adhered today | status, message) — ground truth for attribution checks."""
    from daypart.simmember.dynamics import p_adhered

    return p_adhered(profile.latents, state, intent)


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Spearman rank correlation with tie-averaged ranks; 0.0 when either side is constant."""
    ra, rb = _rankdata(a), _rankdata(b)
    if ra.std() == 0 or rb.std() == 0:
        return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])


def _r6(x: float | None) -> float | None:
    return None if x is None else round(float(x), 6)


def evaluate(cohort_seed: int = 0) -> dict:
    """Held-out-member fit and attribution recovery of the reward model (synthetic only)."""
    cohort = generate(cohort_seed)
    train_fold, held = split(cohort)
    model = trained(cohort_seed)
    test = rollouts(held, cohort_seed=cohort_seed)
    c = model.centred(test.feats)
    p = _sigmoid(_design(c, test.states, test.intents) @ model.weights)

    # Comparators: a constant base rate, and a status + message model with no Jev features.
    train_data = rollouts(train_fold, cohort_seed=cohort_seed)
    base_rate = float(train_data.adhered.mean())
    status_only = _status_only(train_data, test)

    # Attribution recovery: RM lift vs the simulator's true lift, per held-out member × message.
    rm_lift, true_lift, agree = [], [], 0
    for prof in held:
        f = jev.features(jev.answers_for(prof, cohort_seed))
        rm_l = [model.lift(f, i) for i in MESSAGE_INTENTS]
        tr_l = [float(np.mean([true_adherence(prof, s, i) - true_adherence(prof, s, "none") for s in OFF_TRACK]))
                for i in MESSAGE_INTENTS]
        rm_lift += rm_l
        true_lift += tr_l
        agree += int(int(np.argmax(rm_l)) == int(np.argmax(tr_l)))
    rm_arr, tr_arr = np.asarray(rm_lift), np.asarray(true_lift)
    return {
        "data": "synthetic",
        "label": "Simulated SimMember cohort; not clinical evidence.",
        "rm_version": model.version,
        "jev_version": jev.LIBRARY_VERSION,
        "n_parameters": int(model.weights.size),
        "n_components_per_score": 3 + 2 * len(jev.FEATURE_NAMES),
        "train": {"n_members": len(train_fold), "n_rows": model.n_train_rows},
        "heldout": {
            "n_members": len(held),
            "n_rows": int(len(test.adhered)),
            "log_loss": _r6(_log_loss(p, test.adhered)),
            "brier": _r6(float(np.mean((p - test.adhered) ** 2))),
            "auc": _r6(auc(p, test.adhered)),
            "base_rate_log_loss": _r6(_log_loss(np.full(len(test.adhered), base_rate), test.adhered)),
            "status_only_log_loss": _r6(_log_loss(status_only, test.adhered)),
            "status_only_auc": _r6(auc(status_only, test.adhered)),
        },
        "attribution_recovery": {
            "lift_spearman": _r6(_spearman(rm_arr, tr_arr)),
            "lift_pearson": _r6(float(np.corrcoef(rm_arr, tr_arr)[0, 1])),
            "top_message_agreement": _r6(agree / len(held)),
            "top_message_chance": _r6(1.0 / len(MESSAGE_INTENTS)),
        },
    }


def _status_only(train_data: Rollouts, test: Rollouts) -> np.ndarray:
    """Comparator with no Jev features: status × message cells only."""

    def nofeat(d: Rollouts) -> np.ndarray:
        n = len(d.adhered)
        blk = np.concatenate([np.ones((n, 1)), np.eye(len(STATES))[d.states]], axis=1)
        x = np.zeros((n, blk.shape[1] * len(INTENTS)))
        x[:, : blk.shape[1]] = blk
        for j in range(1, len(INTENTS)):
            m = d.intents == j
            x[m, j * blk.shape[1] : (j + 1) * blk.shape[1]] = blk[m]
        return x

    w = fit_logistic(nofeat(train_data), train_data.adhered, L2)
    return _sigmoid(nofeat(test) @ w)


__all__ = [
    "MESSAGE_INTENTS",
    "OFF_TRACK",
    "RM_VERSION",
    "Component",
    "RewardModel",
    "Rollouts",
    "auc",
    "evaluate",
    "heldout",
    "rollouts",
    "split",
    "train",
    "trained",
    "true_adherence",
]

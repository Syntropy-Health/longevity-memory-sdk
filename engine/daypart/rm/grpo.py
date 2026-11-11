"""Plan 4.3 — a small message-type policy trained by GRPO against the reward model.

Smallest honest version (no new spend): the policy is a linear softmax over the seven message
types (:data:`daypart.simmember.dynamics.INTENTS`), conditioned on the member's Jev features and
current status. It is NOT a language model: the text sent for each message type is the fixed,
boundary-checked :data:`daypart.eval.policies.POLICY_TEXT`. Training is Group Relative Policy
Optimisation in numpy on CPU: for each prompt (training-fold member × status) sample a group of
``GROUP`` message types from the current policy, score each with the reward model, use the
group-normalised reward as the advantage, and take an Adam step on
``-E[A·log π] + β·KL(π ‖ uniform)``. Deterministic (seeded rng), synthetic only (I1).

:func:`evaluate_env` measures the greedy policy in the real aviary ``SimMemberEnv`` on exactly
the scenarios the ``env_baseline`` arms use, so the numbers are directly comparable.
"""

from __future__ import annotations

import functools
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from daypart.rm import jev
from daypart.rm.model import RewardModel, split, trained
from daypart.simmember.cohort import Profile, generate
from daypart.simmember.dynamics import INTENTS, STATES

GRPO_VERSION = "grpo-v1"
GROUP = 8
BATCH = 64
STEPS = 300
LR = 0.05
BETA = 0.02
TRAIN_SEED = 4300


@dataclass(frozen=True)
class Policy:
    theta: np.ndarray  # (len(INTENTS), D)
    feature_mean: np.ndarray
    version: str = GRPO_VERSION

    def _x(self, feats: np.ndarray, state: str) -> np.ndarray:
        c = np.asarray(feats, dtype=float) - self.feature_mean
        return np.concatenate([[1.0], c, np.eye(len(STATES))[STATES.index(state)]])

    def probs(self, feats: np.ndarray, state: str) -> np.ndarray:
        return _softmax(self.theta @ self._x(feats, state))

    def act(self, feats: np.ndarray, state: str) -> str:
        """The greedy message type for this member and status."""
        return INTENTS[int(np.argmax(self.probs(feats, state)))]


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


def _inputs(rm: RewardModel, profiles: Sequence[Profile], cohort_seed: int) -> tuple[np.ndarray, np.ndarray]:
    """(raw features, centred features) per profile."""
    raw = np.asarray([jev.features(jev.answers_for(p, cohort_seed)) for p in profiles])
    return raw, rm.centred(raw)


def train_policy(rm: RewardModel, profiles: Sequence[Profile], *, cohort_seed: int = 0,
                 steps: int = STEPS, seed: int = TRAIN_SEED) -> tuple[Policy, dict]:
    """GRPO against ``rm`` on ``profiles`` (synthetic training fold). Returns (policy, training log)."""
    if not profiles:
        raise ValueError("GRPO needs at least one training profile")
    for p in profiles:
        if p.cohort != "synthetic":
            raise ValueError(f"{p.member_id}: GRPO trains on synthetic members only (I1)")
    rng = np.random.default_rng(seed)
    _, cen = _inputs(rm, profiles, cohort_seed)
    n_s, n_a = len(STATES), len(INTENTS)
    d = 1 + cen.shape[1] + n_s
    theta = np.zeros((n_a, d))
    m1, m2 = np.zeros_like(theta), np.zeros_like(theta)
    # The reward for every (member, status, message) is fixed: precompute it once.
    rewards = np.stack([rm.prob_matrix(cen, np.full(len(profiles), s)) for s in range(n_s)], axis=1)  # (P, S, A)
    curve: list[float] = []
    for t in range(1, steps + 1):
        pi_idx = rng.integers(len(profiles), size=BATCH)
        st_idx = rng.integers(n_s, size=BATCH)
        x = np.concatenate([np.ones((BATCH, 1)), cen[pi_idx], np.eye(n_s)[st_idx]], axis=1)  # (B, D)
        pi = _softmax(x @ theta.T)  # (B, A)
        u = rng.random((BATCH, GROUP))
        acts = np.minimum((u[:, :, None] > np.cumsum(pi, axis=1)[:, None, :]).sum(axis=2), n_a - 1)  # (B, G)
        r = rewards[pi_idx[:, None], st_idx[:, None], acts]  # (B, G)
        adv = (r - r.mean(axis=1, keepdims=True)) / (r.std(axis=1, keepdims=True) + 1e-6)
        # ∂(-mean A·log π)/∂logits = -mean_g A·(onehot(a) − π)
        onehot = np.eye(n_a)[acts]  # (B, G, A)
        g_logits = -(adv[:, :, None] * (onehot - pi[:, None, :])).mean(axis=1)  # (B, A)
        logp = np.log(pi + 1e-12)
        g_logits += BETA * pi * (logp - (pi * logp).sum(axis=1, keepdims=True))  # KL(π‖uniform)
        grad = g_logits.T @ x / BATCH
        m1 = 0.9 * m1 + 0.1 * grad
        m2 = 0.999 * m2 + 0.001 * grad**2
        theta -= LR * (m1 / (1 - 0.9**t)) / (np.sqrt(m2 / (1 - 0.999**t)) + 1e-8)
        if t % 50 == 0 or t == 1:
            curve.append(round(float((pi * rewards[pi_idx, st_idx]).sum(axis=1).mean()), 6))
    policy = Policy(theta=theta, feature_mean=rm.feature_mean)
    log = {"steps": steps, "group": GROUP, "batch": BATCH, "lr": LR, "beta_kl": BETA,
           "expected_reward_curve": curve, "curve_every": 50}
    return policy, log


@functools.lru_cache(maxsize=4)
def trained_policy(cohort_seed: int = 0) -> tuple[Policy, dict]:
    train_fold, _ = split(generate(cohort_seed))
    return train_policy(trained(cohort_seed), train_fold, cohort_seed=cohort_seed)


async def _episode(scenario, policy: Policy, feats: np.ndarray) -> tuple[float, bool, float, list[str]]:
    from aviary.core import ToolCall, ToolRequestMessage

    from daypart.eval.policies import POLICY_TEXT
    from daypart.simmember.env import SEND_MESSAGE, SimMemberEnv

    env = SimMemberEnv(scenario)
    await env.reset()
    total, done, steps, used = 0.0, False, 0, []
    while not done:
        intent = policy.act(feats, env.state.member_state)
        used.append(intent)
        call = ToolCall.from_name(SEND_MESSAGE, id=f"d{env.state.day}", text=POLICY_TEXT[intent], intent=intent)
        _, reward, done, _ = await env.step(ToolRequestMessage(tool_calls=[call]))
        total += float(reward)
        steps += 1
        if steps > scenario.horizon + 1:
            raise RuntimeError(f"episode {scenario.scenario_id} did not terminate")
    adh = env.state.adherence
    return (sum(adh) / len(adh)) if adh else 0.0, bool(env.state.violations), total, used


def _r6(x: float) -> float:
    return round(float(x), 6)


def evaluate_env(cohort_seed: int, seeds: Sequence[int], n_scenarios: int, horizon: int) -> dict:
    """The greedy GRPO policy in ``SimMemberEnv`` on the ``env_baseline`` scenarios (all seeds)."""
    from daypart.eval.harness import _drive, _sha256_json, build_scenarios
    from daypart.rm.model import heldout
    from daypart.simmember.env import scenario_manifest

    cohort = generate(cohort_seed)
    policy, log = trained_policy(cohort_seed)
    per_seed, mix = [], dict.fromkeys(INTENTS, 0)
    held_adh: list[float] = []

    async def run_all(scenarios):
        return [await _episode(s, policy, jev.features(jev.answers_for(s.member, cohort_seed))) for s in scenarios]

    for seed in seeds:
        scenarios = build_scenarios(cohort, n_scenarios, seed, horizon)
        eps = _drive(run_all(scenarios))
        for s, e in zip(scenarios, eps):
            for i in e[3]:
                mix[i] += 1
            if heldout(s.member):
                held_adh.append(e[0])
        n = len(eps)
        per_seed.append({
            "seed": seed,
            "n_episodes": n,
            "mean_adherence": _r6(np.mean([e[0] for e in eps]) if n else 0.0),
            "episode_violation_rate": _r6(sum(e[1] for e in eps) / n if n else 0.0),
            "mean_return": _r6(np.mean([e[2] for e in eps]) if n else 0.0),
            "scenario_manifest_sha256": _sha256_json(scenario_manifest(scenarios)),
        })
    total_msgs = sum(mix.values()) or 1
    return {
        "data": "synthetic",
        "label": "Simulated SimMember cohort; not clinical evidence.",
        "grpo_version": policy.version,
        "policy": "linear softmax over message types (not a language model); greedy at eval",
        "horizon": horizon,
        "n_scenarios": n_scenarios,
        "seeds": list(seeds),
        "per_seed": per_seed,
        "mean_adherence": _r6(np.mean([p["mean_adherence"] for p in per_seed])),
        "episode_violation_rate": _r6(np.mean([p["episode_violation_rate"] for p in per_seed])),
        "heldout_members": {"n_episodes": len(held_adh), "mean_adherence": _r6(np.mean(held_adh)) if held_adh else None},
        "message_mix": {i: _r6(mix[i] / total_msgs) for i in INTENTS},
        "training": log,
        "compute": "CPU, numpy; no GPU and no paid API",
    }


__all__ = ["GRPO_VERSION", "Policy", "evaluate_env", "train_policy", "trained_policy"]

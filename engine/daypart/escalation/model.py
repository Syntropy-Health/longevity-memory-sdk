"""Track B — the calibrator, ``fit`` and ``assess`` (``track-b-spec`` interface and decision rule).

The calibrator is an L2-regularised logistic regression over :data:`MODEL_FEATURES`, fitted by
Newton's method (no randomness). Training rows are each training member's history truncated at
:data:`TRAIN_HISTORY_DAYS`; the label is the simulator's hidden ``escalation_trigger != "none"``.
``fit`` is the only place a label is read, and it refuses any curated (held-out) member (I1).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

import numpy as np
import pydantic
from pydantic import ConfigDict, field_validator

from daypart.escalation.features import CRISIS_FEATURE, MODEL_FEATURES, features
from daypart.escalation.history import until
from daypart.simmember.manifest import CuratedLeakError

#: Decision band: fixed constants (4:1 odds either way), never tuned on held-out data.
TAU_LOW = 0.2
TAU_HIGH = 0.8

#: Version of the decision rule (crisis hard gate + the tau band). The membrane rule pack version
#: travels separately in ``Assessment.rule_version``.
DECISION_RULE_VERSION = "escalation-rule-v1"
CALIBRATOR_KIND = "logreg-l2-v1"

#: History lengths (days) each training member contributes a row at.
TRAIN_HISTORY_DAYS: tuple[int, ...] = (14, 28, 42)
L2_PENALTY = 1.0
_MAX_NEWTON = 100
_TOL = 1e-10
_N_REASONS = 3

Decision = Literal["escalate", "no_escalation", "abstain"]


class CuratedMemberError(CuratedLeakError, ValueError):
    """``fit`` was given a curated (held-out) member (I1)."""


class Assessment(pydantic.BaseModel):
    """One escalation verdict. ``text`` is the message the engine would send (escalate only)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    p_escalate: float
    decision: Decision
    reasons: list[str]
    rule_version: str
    calibrator_version: str
    text: str | None = None

    @field_validator("p_escalate")
    @classmethod
    def _unit(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):  # also rejects NaN
            raise ValueError(f"p_escalate={v!r} must be within [0, 1]")
        return v


@dataclass(frozen=True)
class Calibrator:
    feature_names: tuple[str, ...]
    mean: tuple[float, ...]
    scale: tuple[float, ...]
    coef: tuple[float, ...]
    intercept: float
    base_rate: float
    n_train: int
    n_members: int
    seed: int

    @property
    def version(self) -> str:
        payload = {
            "kind": CALIBRATOR_KIND,
            "features": list(self.feature_names),
            "mean": [round(x, 9) for x in self.mean],
            "scale": [round(x, 9) for x in self.scale],
            "coef": [round(x, 9) for x in self.coef],
            "intercept": round(self.intercept, 9),
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        return f"{CALIBRATOR_KIND}:{digest[:12]}"

    def contributions(self, feats: Mapping[str, float]) -> dict[str, float]:
        """Per-feature logit contribution ``coef * standardised value``."""
        return {
            name: c * (float(feats[name]) - m) / s
            for name, m, s, c in zip(self.feature_names, self.mean, self.scale, self.coef)
        }

    def predict(self, feats: Mapping[str, float]) -> float:
        z = self.intercept + sum(self.contributions(feats).values())
        return float(_sigmoid(np.array([z]))[0])


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 0.5 * (1.0 + np.tanh(0.5 * z))  # stable for any z, exactly within [0, 1]


# --------------------------------------------------------------------------- #
# fit
# --------------------------------------------------------------------------- #


def _member_id(m: Any) -> str | None:
    if isinstance(m, str):
        return m
    if isinstance(m, tuple) and m:
        return _member_id(m[0])
    if isinstance(m, Mapping):
        mid = m.get("member_id")
        if mid is None and "profile" in m:
            return _member_id(m["profile"])
        return None if mid is None else str(mid)
    mid = getattr(m, "member_id", None)
    return None if mid is None else str(mid)


def _is_curated(m: Any, mid: str | None) -> bool:
    from daypart.simmember.cohort import CURATED_PROFILES
    from daypart.simmember.narrative import is_curated_profile

    curated_ids = {p.member_id for p in CURATED_PROFILES}
    if mid is not None and (mid.startswith("cur-") or mid in curated_ids):
        return True
    profile = m[0] if isinstance(m, tuple) and m else (m.get("profile") if isinstance(m, Mapping) else m)
    if type(profile).__name__ == "Profile" and is_curated_profile(profile):
        return True
    if getattr(profile, "cohort", None) == "curated" or (isinstance(profile, Mapping) and profile.get("cohort") == "curated"):
        return True
    return False


def _resolve(members: Any, seed: int) -> list[tuple[str, bool, Any]]:
    """``(member_id, label, trajectory)`` per member, after refusing every curated one (I1)."""
    from daypart.simmember.cohort import Cohort, Profile, generate
    from daypart.simmember.trajectory import Trajectory, generate_trajectory

    if isinstance(members, Cohort):
        members = [(p, members.trajectories[p.member_id]) for p in members.training_profiles()]
    items = list(members)
    if not items:
        raise ValueError("fit needs at least one training member")
    curated: set[str] = set()
    for m in items:
        mid = _member_id(m)
        if _is_curated(m, mid):
            curated.add(mid or "<unnamed>")
    if curated:
        raise CuratedMemberError(f"fit refuses curated (held-out) members (I1): {', '.join(sorted(curated))}")

    cohort_cache: list[Any] = []

    def lookup(mid: str) -> tuple[Any, Any]:
        if not cohort_cache:
            cohort_cache.append(generate(seed))
        c = cohort_cache[0]
        prof = next((p for p in c.training_profiles() if p.member_id == mid), None)
        if prof is None:
            raise ValueError(f"unknown training member id {mid!r} for seed {seed}")
        return prof, c.trajectories[mid]

    out: list[tuple[str, bool, Any]] = []
    for m in items:
        traj = None
        if isinstance(m, str):
            prof, traj = lookup(m)
        elif isinstance(m, tuple):
            prof, traj = m[0], (m[1] if len(m) > 1 else None)
        elif isinstance(m, Mapping):
            prof = Profile.model_validate(m.get("profile", m) if "profile" in m else dict(m))
            traj = m.get("trajectory")
        else:
            prof = m
        if not isinstance(prof, Profile):
            prof = Profile.model_validate(prof)
        if traj is None:
            traj = generate_trajectory(prof.member_id, prof.latents, seed)
        elif isinstance(traj, Mapping):
            traj = Trajectory.model_validate(traj)
        if getattr(traj, "member_id", prof.member_id) != prof.member_id:
            raise ValueError(f"trajectory {traj.member_id!r} does not belong to {prof.member_id!r}")
        out.append((prof.member_id, prof.latents.escalation_trigger != "none", traj))
    return out


def training_rows(members: Any, seed: int) -> list[dict[str, Any]]:
    """The rows ``fit`` trains on: ``member_id``, history length, features and label (I1-checked)."""
    rows = []
    for mid, label, traj in _resolve(members, seed):
        n = len(traj.days)
        for length in sorted({min(d, n) for d in TRAIN_HISTORY_DAYS if n}):
            rows.append(
                {"member_id": mid, "history_days": length, "features": features(until(traj, length - 1)), "label": label}
            )
    return rows


def _newton(x: np.ndarray, y: np.ndarray, penalty: float) -> np.ndarray:
    w = np.zeros(x.shape[1])
    reg = np.full(x.shape[1], penalty)
    reg[0] = 0.0  # intercept is not penalised
    for _ in range(_MAX_NEWTON):
        p = _sigmoid(x @ w)
        grad = x.T @ (p - y) + reg * w
        hess = (x * (p * (1.0 - p))[:, None]).T @ x + np.diag(reg) + 1e-9 * np.eye(x.shape[1])
        step = np.linalg.solve(hess, grad)
        w = w - step
        if float(np.max(np.abs(step))) < _TOL:
            break
    return w


def fit(members: Any, seed: int) -> Calibrator:
    """Fit the calibrator on training (synthetic) members only; any curated member raises (I1).

    ``members``: a ``Cohort`` (its training profiles are used), or an iterable of ``Profile``,
    ``(Profile, Trajectory)`` pairs, or synthetic member ids. A profile without a trajectory gets
    the baseline trajectory ``seed`` generates for it.
    """
    rows = training_rows(members, seed)
    if not rows:
        raise ValueError("fit needs at least one non-empty training history")
    x_raw = np.array([[r["features"][f] for f in MODEL_FEATURES] for r in rows], dtype=float)
    y = np.array([1.0 if r["label"] else 0.0 for r in rows])
    mean = x_raw.mean(axis=0)
    scale = x_raw.std(axis=0)
    scale = np.where(scale > 1e-12, scale, 1.0)
    x = np.hstack([np.ones((len(rows), 1)), (x_raw - mean) / scale])
    w = _newton(x, y, L2_PENALTY)
    return Calibrator(
        feature_names=MODEL_FEATURES,
        mean=tuple(float(v) for v in mean),
        scale=tuple(float(v) for v in scale),
        coef=tuple(float(v) for v in w[1:]),
        intercept=float(w[0]),
        base_rate=float(y.mean()),
        n_train=len(rows),
        n_members=len({r["member_id"] for r in rows}),
        seed=int(seed),
    )


# --------------------------------------------------------------------------- #
# assess
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=1)
def _texts() -> tuple[str, str]:
    """(model escalate text, crisis escalate text), both checked by the membrane DSL once."""
    from daypart.checkin.crisis import HANDOFF_TEXT
    from daypart.eval.policies import POLICY_TEXT
    from daypart.membrane import dsl

    handoff = POLICY_TEXT["clinician_handoff"]
    if not dsl.check(handoff).passed or not dsl.check(HANDOFF_TEXT, crisis_context=True).passed:
        raise RuntimeError("escalation text fails membrane.dsl.check()")
    return handoff, HANDOFF_TEXT


def decide(p: float) -> Decision:
    """The tau band for a model probability (the crisis gate is applied before this)."""
    if p >= TAU_HIGH:
        return "escalate"
    if p <= TAU_LOW:
        return "no_escalation"
    return "abstain"


def assess(history: Any, calibrator: Calibrator) -> Assessment:
    """Escalate / stay silent / abstain for one member's observables up to day *t*."""
    from daypart.membrane.dsl import RULE_VERSION

    if not isinstance(calibrator, Calibrator):
        raise TypeError(f"assess needs a fitted Calibrator, got {type(calibrator).__name__}")
    feats = features(history)
    handoff, crisis_text = _texts()
    if feats[CRISIS_FEATURE] > 0:
        return Assessment(
            p_escalate=1.0,
            decision="escalate",
            reasons=[CRISIS_FEATURE],
            rule_version=RULE_VERSION,
            calibrator_version=calibrator.version,
            text=crisis_text,
        )
    p = min(1.0, max(0.0, calibrator.predict(feats)))
    decision = decide(p)
    contrib = calibrator.contributions(feats)
    ranked = sorted(contrib.items(), key=lambda kv: (-abs(kv[1]), kv[0]))
    return Assessment(
        p_escalate=p,
        decision=decision,
        reasons=[name for name, _ in ranked[:_N_REASONS]],
        rule_version=RULE_VERSION,
        calibrator_version=calibrator.version,
        text=handoff if decision == "escalate" else None,
    )


__all__ = [
    "CALIBRATOR_KIND",
    "DECISION_RULE_VERSION",
    "L2_PENALTY",
    "TAU_HIGH",
    "TAU_LOW",
    "TRAIN_HISTORY_DAYS",
    "Assessment",
    "Calibrator",
    "CuratedMemberError",
    "assess",
    "decide",
    "fit",
    "training_rows",
]

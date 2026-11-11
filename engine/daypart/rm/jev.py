"""Plan 4.1 — the Jev question library: short check-in questions that elicit inclination signals.

Each question probes one SimMember inclination (a latent axis, :mod:`daypart.simmember.latents`).
For a synthetic member the answers are *simulated* from its hidden latents with seeded noise:
a member answers truthfully with probability :data:`TRUTH_RATE` (higher with higher health
literacy) and otherwise picks another option uniformly. Answers become a fixed, named feature
vector (:func:`features`) that the reward model (:mod:`.model`) reads. Nothing here sees a
real person: synthetic data only (I1), no identity (I7), deterministic, no network.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

import numpy as np
import pydantic
from pydantic import ConfigDict, model_validator

from daypart.simmember.cohort import Profile
from daypart.simmember.dynamics import member_key
from daypart.simmember.latents import AXES, Latents

LIBRARY_VERSION = "jev-v1"
_JEV_STREAM = 5  # distinct from daypart.simmember.dynamics._STREAMS (0..4)
_MASK64 = (1 << 64) - 1

#: P(truthful answer) by health literacy; otherwise another option is chosen uniformly.
TRUTH_RATE: Mapping[str, float] = MappingProxyType({"low": 0.70, "medium": 0.80, "high": 0.88})

#: Mood answers (1 = low, 5 = good) and the affect value each stands for.
MOOD_SCALE: tuple[float, ...] = (-0.8, -0.4, 0.0, 0.4, 0.8)


class Question(pydantic.BaseModel):
    """One Jev question. ``options`` maps each latent level to the member-facing option text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    question_id: str
    axis: str  # a latents axis, or "affect_baseline" for the mood scale
    text: str
    options: tuple[tuple[str, str], ...]  # (level, option text)

    @model_validator(mode="after")
    def _check(self) -> Question:
        levels = tuple(level for level, _ in self.options)
        if self.axis == "affect_baseline":
            if levels != tuple(str(i) for i in range(1, len(MOOD_SCALE) + 1)):
                raise ValueError("the mood question options are 1..5")
        elif self.axis not in AXES or set(levels) != set(AXES[self.axis]):
            raise ValueError(f"{self.question_id}: options must cover exactly the levels of {self.axis!r}")
        return self


_BARRIER_OPTIONS = (
    ("time", "Not enough time in the day"),
    ("cost", "The cost"),
    ("forgetfulness", "I forget"),
    ("side_effect_concern", "Worry about how it makes me feel"),
    ("social", "The people around me"),
    ("low_energy", "Feeling too tired"),
)

QUESTIONS: tuple[Question, ...] = (
    Question(question_id="jev.barrier", axis="barrier_type",
             text="When your routine slips, what usually gets in the way?", options=_BARRIER_OPTIONS),
    Question(question_id="jev.barrier_help", axis="barrier_type",
             text="Which change would make your routine easiest to keep?",
             options=(("time", "A version that takes less time"), ("cost", "A lower-cost option"),
                      ("forgetfulness", "A reminder at the right moment"),
                      ("side_effect_concern", "Clearer information about how it may feel"),
                      ("social", "Support from the people around me"),
                      ("low_energy", "A lighter version for low-energy days"))),
    Question(question_id="jev.motivation", axis="motivation",
             text="How much does keeping this routine matter to you right now?",
             options=(("low", "Not much at the moment"), ("moderate", "Somewhat"), ("high", "A lot"))),
    Question(question_id="jev.rhythm", axis="engagement_pattern",
             text="Which best describes how your week usually goes?",
             options=(("steady", "Much the same every day"), ("weekend_dip", "Weekends are harder"),
                      ("burst", "I go in bursts"), ("fading", "I start strong, then it fades"),
                      ("erratic", "It changes a lot from day to day"))),
    Question(question_id="jev.literacy", axis="literacy",
             text="How confident do you feel reading health information?",
             options=(("low", "Not very confident"), ("medium", "Fairly confident"), ("high", "Very confident"))),
    Question(question_id="jev.reach_out", axis="escalation_trigger",
             text="What would most make you want to talk to your care team?",
             options=(("none", "Nothing in particular"), ("symptom_flare", "When symptoms flare up"),
                      ("mood_drop", "When my mood drops"), ("missed_streak", "After missing several days"),
                      ("conflicting_info", "When I hear conflicting information"))),
    Question(question_id="jev.mood", axis="affect_baseline",
             text="How has your mood been over the past week, from 1 (low) to 5 (good)?",
             options=tuple((str(i), str(i)) for i in range(1, len(MOOD_SCALE) + 1))),
)

QUESTION_IDS: tuple[str, ...] = tuple(q.question_id for q in QUESTIONS)
_BY_ID: Mapping[str, Question] = MappingProxyType({q.question_id: q for q in QUESTIONS})

#: Categorical feature groups: (feature prefix, axis, the questions that feed it).
_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("barrier", "barrier_type", ("jev.barrier", "jev.barrier_help")),
    ("motivation", "motivation", ("jev.motivation",)),
    ("rhythm", "engagement_pattern", ("jev.rhythm",)),
    ("literacy", "literacy", ("jev.literacy",)),
    ("reach_out", "escalation_trigger", ("jev.reach_out",)),
)

#: The named feature vector, in a fixed order: one share per level of each group, then ``mood``.
FEATURE_NAMES: tuple[str, ...] = tuple(
    f"{prefix}.{level}" for prefix, axis, _ in _GROUPS for level in AXES[axis]
) + ("mood",)

Answers = Mapping[str, str]


def _rng(seed: int, member_id: str) -> np.random.Generator:
    return np.random.default_rng([int(seed) & _MASK64, _JEV_STREAM, *member_key(member_id)])


def _mood_answer(affect: float) -> str:
    return str(int(np.argmin([abs(affect - m) for m in MOOD_SCALE])) + 1)


def simulate_answers(latents: Latents, member_id: str, seed: int = 0) -> dict[str, str]:
    """The answers a simulated member gives to every Jev question (seeded by ``seed`` + member)."""
    rng = _rng(seed, member_id)
    truth = TRUTH_RATE[latents.literacy]
    out: dict[str, str] = {}
    for q in QUESTIONS:  # fixed order → fixed number of draws per question
        u, pick = rng.random(), rng.random()
        if q.axis == "affect_baseline":
            true_level = _mood_answer(latents.affect_baseline)
        else:
            true_level = getattr(latents, q.axis)
        levels = [level for level, _ in q.options]
        if u < truth:
            out[q.question_id] = true_level
        else:
            others = [lvl for lvl in levels if lvl != true_level]
            out[q.question_id] = others[min(int(pick * len(others)), len(others) - 1)]
    return out


def answers_for(profile: Profile, seed: int = 0) -> dict[str, str]:
    """Simulated Jev answers for a synthetic profile."""
    return simulate_answers(profile.latents, profile.member_id, seed)


def validate_answers(answers: Answers) -> None:
    """``ValueError`` unless every question is answered with one of its options."""
    missing = [qid for qid in QUESTION_IDS if qid not in answers]
    if missing:
        raise ValueError(f"unanswered Jev questions: {missing}")
    for qid, value in answers.items():
        q = _BY_ID.get(qid)
        if q is None:
            raise ValueError(f"unknown Jev question {qid!r}")
        if value not in {level for level, _ in q.options}:
            raise ValueError(f"{qid}: {value!r} is not one of its options")


def features(answers: Answers) -> np.ndarray:
    """The named feature vector (:data:`FEATURE_NAMES` order) for one member's answers."""
    validate_answers(answers)
    vec: list[float] = []
    for _, axis, qids in _GROUPS:
        for level in AXES[axis]:
            vec.append(sum(1.0 for qid in qids if answers[qid] == level) / len(qids))
    vec.append(MOOD_SCALE[int(answers["jev.mood"]) - 1])
    return np.asarray(vec, dtype=float)


def infer_latents(answers: Answers) -> dict[str, str]:
    """The most likely level of each categorical axis given the answers (ties → first level)."""
    f = features(answers)
    out: dict[str, str] = {}
    i = 0
    for _, axis, _ in _GROUPS:
        levels = AXES[axis]
        block = f[i : i + len(levels)]
        out[axis] = levels[int(np.argmax(block))]
        i += len(levels)
    return out


def recovery(profiles: Sequence[Profile], seed: int = 0) -> dict:
    """How well the simulated answers recover each hidden axis (the ``jev`` eval arm)."""
    if not profiles:
        raise ValueError("recovery needs at least one profile")
    hits = {axis: 0 for _, axis, _ in _GROUPS}
    mood_err = 0.0
    for p in profiles:
        answers = answers_for(p, seed)
        guess = infer_latents(answers)
        for axis in hits:
            hits[axis] += int(guess[axis] == getattr(p.latents, axis))
        mood_err += abs(MOOD_SCALE[int(answers["jev.mood"]) - 1] - p.latents.affect_baseline)
    n = len(profiles)
    chance = {axis: round(1.0 / len(AXES[axis]), 6) for axis in hits}
    return {
        "n_members": n,
        "axis_accuracy": {axis: round(hits[axis] / n, 6) for axis in sorted(hits)},
        "chance_accuracy": {axis: chance[axis] for axis in sorted(chance)},
        "mood_mean_abs_error": round(mood_err / n, 6),
    }


__all__ = [
    "FEATURE_NAMES",
    "LIBRARY_VERSION",
    "MOOD_SCALE",
    "QUESTIONS",
    "QUESTION_IDS",
    "TRUTH_RATE",
    "Question",
    "answers_for",
    "features",
    "infer_latents",
    "recovery",
    "simulate_answers",
    "validate_answers",
]

"""Inclinations: what the reward model says drives a member, turned into next steps with reasons.

Input: one member's Jev answers. Output (:class:`Inclinations`):

- ``drivers`` — the answers that weigh most on keeping the routine, each with a plain-language
  label, a direction (``helps`` / ``makes_harder``) and a word-tier weight (``strong`` / ``moderate``
  / ``slight``, from its share of the explained effect). A
  driver's weight is the size of its reward-model terms (member part + the message terms of the
  member's top message types), compared with a typical simulated member.
- ``insights`` — 1–3 concrete next steps. Each is a message type whose estimated lift is
  positive, phrased as an action, with the reason shown and a link (``driver``) to the answer
  that supports it most.

Every member-facing string passes ``assert_narration_safe`` and the boundary DSL (fail closed:
a string that fails is never shown). Estimates come from simulated members only.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Literal

import numpy as np
import pydantic
from pydantic import ConfigDict, model_validator

from daypart.rm import jev
from daypart.rm.model import MESSAGE_INTENTS, OFF_TRACK, RewardModel

MAX_DRIVERS = 3
MAX_INSIGHTS = 3
MIN_LIFT = 0.005  # half a percentage point
#: A message term (logit) at least this large counts as a personal link to the answer.
LINK_MIN = 0.12
#: The answer group each message type speaks to, used when no personal term is strong enough.
NATURAL_GROUP: Mapping[str, str] = MappingProxyType({
    "reminder": "barrier", "encouragement": "motivation", "barrier_problem_solving": "barrier",
    "celebrate_streak": "rhythm", "check_in_question": "rhythm", "clinician_handoff": "reach_out",
})
#: Word tiers instead of numbers: the passport carries no free-floating numbers (T6.5: no value
#: there may be mistaken for a registry bound). The numbers themselves are in the ``rm`` eval arm.
WEIGHT_TIERS: tuple[tuple[float, str], ...] = ((0.4, "strong"), (0.2, "moderate"), (0.0, "slight"))
LIFT_TIERS: tuple[tuple[float, str], ...] = ((0.08, "clear"), (0.03, "moderate"), (0.0, "small"))
_LIFT_PHRASE = {"clear": "a clear gain", "moderate": "a moderate gain", "small": "a small gain"}


def _tier(x: float, tiers: tuple[tuple[float, str], ...]) -> Any:
    return next(name for lo, name in tiers if x >= lo)


SOURCE_NOTE = (
    "Estimated from simulated members, not from patient data. "
    "These are prompts to discuss with your care team, not a care plan."
)

#: Plain-language label per Jev feature (second person, as the member reads it).
FEATURE_LABELS: Mapping[str, str] = MappingProxyType({
    "barrier.time": "Time is what most often gets in the way",
    "barrier.cost": "Cost is what most often gets in the way",
    "barrier.forgetfulness": "Forgetting is what most often gets in the way",
    "barrier.side_effect_concern": "Worry about how the routine makes you feel",
    "barrier.social": "The people around you affect your routine",
    "barrier.low_energy": "Low energy is what most often gets in the way",
    "motivation.low": "The routine matters less to you right now",
    "motivation.moderate": "The routine matters to you somewhat",
    "motivation.high": "The routine matters a lot to you",
    "rhythm.steady": "Your days follow a steady pattern",
    "rhythm.weekend_dip": "Weekends are harder for you",
    "rhythm.burst": "You tend to go in bursts",
    "rhythm.fading": "You start strong, then it tends to fade",
    "rhythm.erratic": "Your days vary a lot",
    "literacy.low": "Health information can be hard to read",
    "literacy.medium": "You are fairly confident with health information",
    "literacy.high": "You are confident with health information",
    "reach_out.none": "Nothing in particular makes you want to reach out",
    "reach_out.symptom_flare": "Symptom flare-ups make you want to reach out",
    "reach_out.mood_drop": "A drop in mood makes you want to reach out",
    "reach_out.missed_streak": "Missing several days makes you want to reach out",
    "reach_out.conflicting_info": "Conflicting information makes you want to reach out",
    "mood": "Your recent mood",
})

#: The action and its short title per message type (healthcare-professional wording).
INSIGHT_TEXT: Mapping[str, tuple[str, str]] = MappingProxyType({
    "reminder": ("A reminder at the right moment",
                 "Set a short reminder for the time of day the routine usually happens."),
    "encouragement": ("Encouragement that notices effort",
                      "A brief message that recognises the effort so far tends to help on harder days."),
    "barrier_problem_solving": ("Plan around what gets in the way",
                                "Talk through what got in the way and agree one small change that fits the day."),
    "celebrate_streak": ("Mark the days kept",
                         "Mark each run of days kept, so the habit is easier to hold on to."),
    "check_in_question": ("A short weekly check-in",
                          "A short question about how the week is going keeps the routine in view."),
    "clinician_handoff": ("Talk it through with your care team",
                          "When a concern comes up, a conversation with your care team is a good next step."),
})


def _safe(text: str) -> bool:
    from daypart.membrane import dsl
    from syntropy.lhm.metrics.claims import assert_narration_safe

    try:
        assert_narration_safe(text)
    except Exception:
        return False
    return bool(dsl.check(text).passed)


class Driver(pydantic.BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    driver_id: str  # the Jev feature name, e.g. "barrier.forgetfulness"
    label: str
    direction: Literal["helps", "makes_harder"]
    weight: Literal["strong", "moderate", "slight"]  # tier of its share of the summed driver weight
    question_ids: tuple[str, ...]  # the Jev questions this answer came from

    @model_validator(mode="after")
    def _check(self) -> Driver:
        if not _safe(self.label):
            raise ValueError("driver label failed the narration guard")
        return self


class Insight(pydantic.BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    insight_id: str  # "insight:<message type>"
    title: str
    action: str
    reason: str
    driver: str  # a Driver.driver_id in the same Inclinations
    strength: Literal["clear", "moderate", "small"]  # tier of the estimated lift (see LIFT_TIERS)

    @model_validator(mode="after")
    def _check(self) -> Insight:
        for text in (self.title, self.action, self.reason):
            if not _safe(text):
                raise ValueError("insight text failed the narration guard")
        return self


class Inclinations(pydantic.BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: Literal["Inclinations"] = "Inclinations"
    data: Literal["synthetic"] = "synthetic"
    rm_version: str
    jev_version: str
    drivers: tuple[Driver, ...]
    insights: tuple[Insight, ...]
    note: str = SOURCE_NOTE

    @model_validator(mode="after")
    def _check(self) -> Inclinations:
        ids = {d.driver_id for d in self.drivers}
        missing = [i.insight_id for i in self.insights if i.driver not in ids]
        if missing:
            raise ValueError(f"insights not linked to a shown driver: {missing}")
        if len(self.insights) > MAX_INSIGHTS:
            raise ValueError("at most three insights")
        if not _safe(self.note):
            raise ValueError("note failed the narration guard")
        return self


_QUESTIONS_FOR = {"barrier": ("jev.barrier", "jev.barrier_help"), "motivation": ("jev.motivation",),
                  "rhythm": ("jev.rhythm",), "literacy": ("jev.literacy",), "reach_out": ("jev.reach_out",),
                  "mood": ("jev.mood",)}


def _terms(rm: RewardModel, feats: np.ndarray, intent: str) -> dict[str, tuple[float, float]]:
    """Per feature: (member term, message term) averaged over off-track statuses."""
    acc: dict[str, list[float]] = {n: [0.0, 0.0] for n in jev.FEATURE_NAMES}
    for s in OFF_TRACK:
        for comp in rm.attribution(feats, s, intent):
            if comp.name in acc:
                acc[comp.name][0 if comp.part == "member" else 1] += comp.value / len(OFF_TRACK)
    return {k: (v[0], v[1]) for k, v in acc.items()}


def inclinations(rm: RewardModel, answers: Mapping[str, str]) -> Inclinations:
    """Drivers and next steps for one member's Jev answers (deterministic)."""
    feats = jev.features(answers)
    present = {name for name, v in zip(jev.FEATURE_NAMES, feats) if v > 0.0 or name == "mood"}
    lifts = {i: rm.lift(feats, i) for i in MESSAGE_INTENTS}
    ranked = sorted(MESSAGE_INTENTS, key=lambda i: (-lifts[i], i))
    chosen = [i for i in ranked if lifts[i] >= MIN_LIFT and _safe(INSIGHT_TEXT[i][1])][:MAX_INSIGHTS]
    if not chosen and lifts[ranked[0]] > 0.0:
        chosen = [ranked[0]]

    terms = {i: _terms(rm, feats, i) for i in MESSAGE_INTENTS}
    member_term = terms[MESSAGE_INTENTS[0]]  # the member part does not depend on the message type
    weight = {
        k: abs(member_term[k][0]) + max((abs(terms[i][k][1]) for i in chosen), default=0.0)
        for k in present
    }
    links: dict[str, str] = {}
    personal: dict[str, bool] = {}
    for i in chosen:
        best = max(sorted(present), key=lambda k: terms[i][k][1])  # strongest message term; ties by name
        if terms[i][best][1] >= LINK_MIN:
            links[i], personal[i] = best, True
        else:  # a general effect: link to the member's own answer in the group this message speaks to
            group = [k for k in jev.FEATURE_NAMES if k.split(".")[0] == NATURAL_GROUP[i]]
            links[i] = max(group, key=lambda k: (feats[jev.FEATURE_NAMES.index(k)], -group.index(k)))
            personal[i] = False
    # A general effect whose only link is a "nothing in particular" answer is not shown.
    chosen = [i for i in chosen if personal[i] or not links[i].endswith(".none")]

    order = sorted(present, key=lambda k: (-weight[k], k))
    shown: list[str] = []
    for k in [*dict.fromkeys(links[i] for i in chosen), *order]:
        if k not in shown and _safe(FEATURE_LABELS[k]):
            shown.append(k)
    shown = shown[: max(MAX_DRIVERS, len(set(links.values())))]
    for k in shown:
        weight.setdefault(k, 0.0)
    total = sum(weight[k] for k in shown) or 1.0
    shown.sort(key=lambda k: (-weight[k], k))

    drivers = tuple(
        Driver(
            driver_id=k,
            label=FEATURE_LABELS[k],
            direction="helps" if member_term[k][0] >= 0 else "makes_harder",
            weight=_tier(weight[k] / total, WEIGHT_TIERS),
            question_ids=_QUESTIONS_FOR[k.split(".")[0]],
        )
        for k in shown
    )
    insights = []
    for i in chosen:
        title, action = INSIGHT_TEXT[i]
        strength = _tier(lifts[i], LIFT_TIERS)
        if personal[i]:
            basis = "Among simulated members who answered like you"
        else:
            basis = "Across most simulated members, including those who answered like you"
        reason = (
            f"Why: {FEATURE_LABELS[links[i]]}. {basis}, this kind of message was linked to "
            f"{_LIFT_PHRASE[strength]} in days with the routine kept, on days when it was slipping."
        )
        insights.append(Insight(insight_id=f"insight:{i}", title=title, action=action, reason=reason,
                                driver=links[i], strength=strength))
    return Inclinations(rm_version=rm.version, jev_version=jev.LIBRARY_VERSION,
                        drivers=drivers, insights=tuple(insights))


__all__ = ["FEATURE_LABELS", "INSIGHT_TEXT", "Driver", "Inclinations", "Insight", "inclinations"]

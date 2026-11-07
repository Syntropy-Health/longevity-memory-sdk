"""The suggested next step after a saved check-in (A&D §4.7, R7; policy ``next-step-v1``).

Selection is deterministic and reads no clinical value: from the journal's last saved check-in and
its adherence state, the first rule that applies wins.

1. A ``symptoms_wellbeing`` observation saved in that check-in -> ``clinician_handoff`` (pain or
   mood reports always route to a person, whatever the value).
2. Adherence missed on 2 of the last 3 days -> ``barrier_problem_solving``.
3. An adherence streak of 3 or more days ending today -> ``celebrate_streak``.
4. Otherwise ``check_in_question``.

The step text is ``POLICY_TEXT[intent]``, read when the step is built, and the reason is a fixed
template that names the triggering concept, never its value. Text and reason must pass
``membrane.post()`` (layer 0, then ``dsl.check``); on any violation the step is replaced by the
clinician-handoff text, labelled "Ask a professional", with ``replaced=True``. "choose" appends one
``ActionEvent act:goal_set`` (once per step); "defer" and "ask_professional" write nothing (J1).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import pydantic
from pydantic import ConfigDict

from daypart.checkin.journal import Journal
from daypart.checkin.models import CheckIn
from daypart.demo.safety import safe_text
from daypart.eval import policies
from daypart.eval.policies import POLICY_TEXT
from daypart.membrane import dsl
from daypart.membrane.post import post
from daypart.memory.events import ActionEvent, SignalEvent
from daypart.memory.lhm import SERIES_NODES
from daypart.memory.registry import load_registry

POLICY_VERSION = "next-step-v1"
OPTIONS: tuple[str, str, str] = ("choose", "defer", "ask_professional")
Choice = Literal["choose", "defer", "ask_professional"]
Intent = Literal["clinician_handoff", "barrier_problem_solving", "celebrate_streak", "check_in_question"]

ADHERENCE_CODE = "dp:adherence.protocol"
GOAL_SET = "act:goal_set"
SYMPTOM_VERTICAL = "symptoms_wellbeing"
MISS_WINDOW_DAYS = 3
MISSES_FOR_BARRIER = 2
STREAK_FOR_CELEBRATE = 3

# Captured at import from the boundary-safe library, so a replaced step never reads patched text.
HANDOFF_TEXT: str = POLICY_TEXT["clinician_handoff"]
_LIBRARY = POLICY_TEXT
STEP_LABEL = "Suggested next step"
ASK_PROFESSIONAL_LABEL = "Ask a professional"

_SYMPTOM_FALLBACK = "a symptom or wellbeing score"
_REASONS: Mapping[str, str] = {
    "clinician_handoff": "Your last check-in included {concept}. Reports like this always go to a person.",
    "barrier_problem_solving": "Your protocol adherence record shows missed days in the last three days.",
    "celebrate_streak": "Your protocol adherence record shows several days in a row.",
    "check_in_question": "Your last check-in is saved. A short question keeps your record current.",
}
REPLACED_REASON = "The suggested step did not pass the safety check, so it goes to a person instead."


class NoSavedCheckin(LookupError):
    status = 409
    body: Mapping[str, str] = {"error": "no_saved_checkin"}


class UnknownStep(LookupError):
    status = 422
    body: Mapping[str, str] = {"error": "unknown_step"}


class Membrane(pydantic.BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    decision: Literal["pass", "escalate"]
    rule_hits: tuple[str, ...]


class NextStep(pydantic.BaseModel):
    """A&D §4.7 ``NextStep``, plus ``label`` ("Ask a professional" when replaced)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    step_id: str
    text: str
    reason: str
    intent: Intent
    label: str
    membrane: Membrane
    options: tuple[str, str, str] = OPTIONS
    replaced: bool


@dataclass(frozen=True)
class AdherenceDay:
    date: dt.date
    value: float  # 1.0 adhered, 0.0 missed (the simulated series and the slice's plausible bounds)


@dataclass(frozen=True)
class Selection:
    intent: Intent
    reason: str


def _library() -> Mapping[str, str]:
    """The step library: this module's ``POLICY_TEXT``, or ``daypart.eval``'s if that was replaced."""
    return POLICY_TEXT if POLICY_TEXT is not _LIBRARY else policies.POLICY_TEXT


def _streak(by_date: Mapping[dt.date, float], today: dt.date) -> int:
    n = 0
    while by_date.get(today - dt.timedelta(days=n)) == 1.0:
        n += 1
    return n


def select_intent(symptom: str | None, days: Sequence[AdherenceDay], *, today: dt.date) -> Selection:
    """§4.7 rules in order. ``symptom`` is the label of the first symptoms/wellbeing concept saved in
    the last check-in (None if none); ``days`` is the adherence record (a later entry wins a date)."""
    if symptom is not None:
        return Selection("clinician_handoff", _REASONS["clinician_handoff"].format(concept=symptom))
    by_date: dict[dt.date, float] = {}
    for d in days:
        if d.date <= today:
            by_date[d.date] = d.value
    window = [by_date.get(today - dt.timedelta(days=k)) for k in range(MISS_WINDOW_DAYS)]
    if sum(1 for v in window if v == 0.0) >= MISSES_FOR_BARRIER:
        return Selection("barrier_problem_solving", _REASONS["barrier_problem_solving"])
    if _streak(by_date, today) >= STREAK_FOR_CELEBRATE:
        return Selection("celebrate_streak", _REASONS["celebrate_streak"])
    return Selection("check_in_question", _REASONS["check_in_question"])


# --- journal reads -------------------------------------------------------------------------------


def last_saved_checkin(journal: Journal) -> CheckIn | None:
    """The check-in saved most recently (by save order; ``checkins`` keeps creation order)."""
    cid = journal.last_saved_checkin_id
    return journal.checkins.get(cid) if cid is not None else None


def _symptom_label(journal: Journal, checkin_id: str) -> str | None:
    reg = load_registry()
    for rec in journal.provenance.values():  # save order
        if rec.provenance.checkin_id != checkin_id or rec.status != "mapped" or rec.concept_id is None:
            continue
        concept = reg.by_concept_id(rec.concept_id)
        if concept is None or concept.vertical != SYMPTOM_VERTICAL:
            continue
        node = journal.ontology.nodes.get(concept.code)
        label = (node.label or node.display) if node is not None else concept.display
        return label if label and safe_text(label) == label else _SYMPTOM_FALLBACK
    return None


def _today_noon(journal: Journal) -> dt.datetime:
    return dt.datetime.combine(journal.today, dt.time(12), dt.timezone.utc)


async def adherence_days(journal: Journal) -> tuple[AdherenceDay, ...]:
    """The member's adherence by day up to today: the simulated series, then any value saved in this
    journal (which wins its day). Values are kept as they are; only 1.0 and 0.0 count in the rules."""
    as_of = _today_noon(journal)
    member_id = journal.member.member_id
    days: list[AdherenceDay] = []
    for rec in await journal.memory.adapter.read_outcome_series(member_id):
        if SERIES_NODES.get(rec.metric_display) != ADHERENCE_CODE:
            continue
        for p in rec.points:
            if p.value is not None and p.observed_at <= as_of:
                days.append(AdherenceDay(p.observed_at.astimezone(dt.timezone.utc).date(), float(p.value)))
    days.sort(key=lambda d: d.date)
    for e in journal.events.events(member_id, as_of=as_of):
        if isinstance(e, SignalEvent) and e.code == ADHERENCE_CODE:
            days.append(AdherenceDay(e.occurred_at.astimezone(dt.timezone.utc).date(), float(e.value)))
    return tuple(days)


def _verdict(texts: Iterable[Any]) -> tuple[bool, Membrane]:
    passed = True
    hits: set[str] = set()
    for t in texts:
        res = post(t)
        if res.decision != "pass":
            passed = False
        hits.update(res.trace["dsl"]["violations"])
        try:  # post() stops at layer 0; run the DSL on its own so its rule hits are always shown
            hits.update(v.rule_id for v in dsl.check(t).violations)
        except Exception:  # noqa: BLE001 - not a string or the DSL failed: fail closed
            passed = False
    return passed, Membrane(decision="pass" if passed else "escalate", rule_hits=tuple(sorted(hits)))


async def suggest(journal: Journal) -> NextStep:
    """The step for the journal's last saved check-in; ``NoSavedCheckin`` before any save."""
    checkin = last_saved_checkin(journal)
    if checkin is None:
        raise NoSavedCheckin(journal.journal_id)
    sel = select_intent(
        _symptom_label(journal, checkin.checkin_id), await adherence_days(journal), today=journal.today
    )
    text = _library().get(sel.intent)
    passed, membrane = _verdict([text, sel.reason])  # a non-string text fails layer 0 (fail closed)
    step_id = f"ns-{checkin.checkin_id}"
    if passed and isinstance(text, str):
        return NextStep(step_id=step_id, text=text, reason=sel.reason, intent=sel.intent, label=STEP_LABEL,
                        membrane=membrane, replaced=False)
    return NextStep(step_id=step_id, text=HANDOFF_TEXT, reason=REPLACED_REASON, intent="clinician_handoff",
                    label=ASK_PROFESSIONAL_LABEL, membrane=membrane, replaced=True)


class ChoiceIn(pydantic.BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    step_id: pydantic.StrictStr
    choice: Choice


async def record_choice(journal: Journal, step_id: str, choice: Choice) -> dict[str, Any]:
    """``{"recorded": event_id | None}``. Only "choose" writes, once per step (J1)."""
    checkin = last_saved_checkin(journal)
    if checkin is None or step_id != f"ns-{checkin.checkin_id}":
        raise UnknownStep(step_id)
    if choice != "choose":
        return {"recorded": None}
    existing = journal.goal_events.get(step_id)
    if existing is not None:
        return {"recorded": existing}
    n = journal.event_count + 1
    event = ActionEvent(event_id=journal.event_id(n), member_id=journal.member.member_id,
                        occurred_at=_today_noon(journal), code=GOAL_SET)
    journal.events.append(event)
    journal.event_count = n
    journal.goal_events[step_id] = event.event_id
    return {"recorded": event.event_id}


__all__ = [
    "ASK_PROFESSIONAL_LABEL",
    "HANDOFF_TEXT",
    "OPTIONS",
    "POLICY_VERSION",
    "AdherenceDay",
    "ChoiceIn",
    "Membrane",
    "NextStep",
    "NoSavedCheckin",
    "Selection",
    "UnknownStep",
    "adherence_days",
    "last_saved_checkin",
    "record_choice",
    "select_intent",
    "suggest",
]

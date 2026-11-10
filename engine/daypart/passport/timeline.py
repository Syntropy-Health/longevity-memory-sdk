"""The continuous-adaptation timeline (HAC-38 AM-2 D3, addendum G33).

``GET /api/journals/{id}/timeline`` shows how the clone adapted, one entry per saved check-in in
save order. Each entry is computed from the real pipeline, never narrated: the EventLog appends the
save made, the Health Clone Passport before and after it, and the suggested next step before and
after it. Nothing here writes to the journal.

How an entry is computed: the journal is cut to its first ``k`` saves (a *prefix view*: the
check-ins, records and events those saves wrote, and nothing else), and the real
:func:`~daypart.passport.view.health_clone_passport` and :func:`~daypart.checkin.next_step.suggest`
run over the prefix views ``k - 1`` and ``k``. Both are judged at the entry's moment: 12:00 UTC on
the latest date the save recorded (never after the journal's ``today``), so a seeded persona's
check-in from three weeks ago shows what it changed then. Next-step choices (``act:goal_set``) are
not part of any save, so they never move the timeline.

A save is immutable once made, so each prefix snapshot is cached on the journal
(``timeline_cache``) and a long journal stays cheap to re-read.
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt
from collections import OrderedDict
from typing import Literal

import pydantic
from pydantic import ConfigDict

from daypart.checkin import next_step
from daypart.checkin.journal import Journal
from daypart.memory.events import EventLog
from daypart.memory.lhm import MemoryLhm
from daypart.passport import view as passport_view

TIMELINE_VERSION = "timeline-v1"

Change = Literal["became_ready", "withheld", "value_changed", "now_observed"]


class Append(pydantic.BaseModel):
    """One EventLog append, with the value as the person recorded it (not the canonical unit)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str
    record_id: str
    concept_id: str
    code: str
    display: str
    value: float
    unit: str
    observed_at: dt.datetime


class CardState(pydantic.BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["ready", "withheld"]
    origin: Literal["observed", "simulated"]
    value: float | None
    unit: str | None


class CardChange(pydantic.BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    card_id: str
    title: str
    change: Change
    before: CardState | None  # None: the card did not exist yet (a pattern card that appeared)
    after: CardState


class StepState(pydantic.BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    step_id: str
    intent: str
    label: str
    text: str


class StepChange(pydantic.BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    before: StepState | None  # None before the first save: there was no step
    after: StepState
    changed: bool


class Entry(pydantic.BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    index: int  # 1-based save number
    checkin_id: str
    as_of: dt.datetime
    appends: tuple[Append, ...]
    passport_changes: tuple[CardChange, ...]
    next_step: StepChange


class Timeline(pydantic.BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Literal["timeline-v1"] = TIMELINE_VERSION
    journal_id: str
    member_id: str
    policy_version: str = next_step.POLICY_VERSION
    entries: tuple[Entry, ...]


@dataclasses.dataclass(frozen=True)
class _Snapshot:
    cards: dict[str, tuple[str, CardState]]  # card_id -> (title, state)
    step: StepState | None


def _noon(day: dt.date) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(12), tzinfo=dt.timezone.utc)


def _prefix(journal: Journal, k: int, today: dt.date) -> Journal:
    """The journal as its first ``k`` saves left it, judged on ``today``. A separate object: the
    journal itself is never touched."""
    saved = journal.saved_order[:k]
    ids = set(saved)
    records = {rid: r for rid, r in journal.provenance.items() if r.provenance.checkin_id in ids}
    event_ids = {r.event_id for r in records.values() if r.event_id is not None}
    events = EventLog(journal.ontology)
    events.extend(e for e in journal.all_events() if e.event_id in event_ids)
    return dataclasses.replace(
        journal,
        events=events,
        memory=MemoryLhm(journal.memory.adapter, ontology=journal.ontology, events=events),
        provenance=records,
        checkins=OrderedDict((cid, c) for cid, c in journal.checkins.items() if cid in ids),
        last_saved_checkin_id=saved[-1] if saved else None,
        saved_order=list(saved),
        goal_events={},
        timeline_cache={},
        lock=asyncio.Lock(),
        today=today,
    )


async def _snapshot(journal: Journal, k: int, day: dt.date) -> _Snapshot:
    key = (k, day)
    hit = journal.timeline_cache.get(key)
    if hit is not None:
        return hit
    view = _prefix(journal, k, day)
    pp = await passport_view.health_clone_passport(view, _noon(day))
    cards = {
        c.card_id: (c.title, CardState(status=c.status, origin=c.origin, value=c.value, unit=c.unit)) for c in pp.cards
    }
    try:
        s = await next_step.suggest(view)
        step: StepState | None = StepState(step_id=s.step_id, intent=s.intent, label=s.label, text=s.text)
    except next_step.NoSavedCheckin:
        step = None
    snap = _Snapshot(cards=cards, step=step)
    journal.timeline_cache[key] = snap
    return snap


def _change(before: CardState | None, after: CardState) -> Change | None:
    if after.status == "ready" and (before is None or before.status == "withheld"):
        return "became_ready"
    if after.status == "withheld":
        return "withheld" if before is not None and before.status == "ready" else None
    assert before is not None
    if before.origin == "simulated" and after.origin == "observed":
        return "now_observed"
    if (before.value, before.unit) != (after.value, after.unit):
        return "value_changed"
    return None


def _entry_day(journal: Journal, checkin_id: str) -> dt.date:
    days = [r.observed_at.astimezone(dt.timezone.utc).date() for r in journal.provenance.values()
            if r.provenance.checkin_id == checkin_id]
    return min(max(days), journal.today) if days else journal.today


async def timeline(journal: Journal) -> Timeline:
    """Every saved check-in's entry, in save order (empty before the first save)."""
    entries: list[Entry] = []
    codes = {e.event_id: getattr(e, "code") for e in journal.all_events()}
    for k, checkin_id in enumerate(journal.saved_order, start=1):
        day = _entry_day(journal, checkin_id)
        before = await _snapshot(journal, k - 1, day)
        after = await _snapshot(journal, k, day)
        changes = []
        for card_id, (title, state) in after.cards.items():
            prior = before.cards.get(card_id)
            change = _change(prior[1] if prior is not None else None, state)
            if change is not None:
                changes.append(CardChange(card_id=card_id, title=title, change=change,
                                          before=prior[1] if prior is not None else None, after=state))
        appends = []
        for rec in journal.provenance.values():  # save order
            if rec.provenance.checkin_id != checkin_id or rec.event_id is None or rec.concept_id is None:
                continue
            assert rec.value is not None and rec.unit is not None  # a mapped record has both
            appends.append(Append(event_id=rec.event_id, record_id=rec.record_id, concept_id=rec.concept_id,
                                  code=codes[rec.event_id], display=rec.display, value=rec.value,
                                  unit=rec.unit, observed_at=rec.observed_at))
        assert after.step is not None  # k >= 1 saves: there is always a step
        step = StepChange(
            before=before.step,
            after=after.step,
            changed=before.step is None or (before.step.intent, before.step.text) != (after.step.intent, after.step.text),
        )
        entries.append(Entry(index=k, checkin_id=checkin_id, as_of=_noon(day), appends=tuple(appends),
                             passport_changes=tuple(changes), next_step=step))
    return Timeline(journal_id=journal.journal_id, member_id=journal.member.member_id, entries=tuple(entries))


__all__ = ["TIMELINE_VERSION", "Append", "CardChange", "CardState", "Entry", "StepChange", "StepState",
           "Timeline", "timeline"]

"""The seeded persona (HAC-38 AM-2 D2, addendum G32).

The member app opens on a prepared journal instead of an empty one: one fictional member
(``persona_v1.json``, made by ``tools/make_persona.py``) whose 28 days of check-ins are replayed
through the real service, :func:`~daypart.checkin.service.create_checkin` then
:func:`~daypart.checkin.service.review` with every proposal confirmed. Nothing is written around the
pipeline, so the passport, next step and timeline of a seeded journal are computed exactly as for a
person's own journal. The persona is fictional in the data (``fictional: true``, its ``note``) and
its journal is a ``syn-`` member's like any other (I1). A fresh, empty journal stays available.

A check-in that does not replay cleanly (a handoff, a refusal, a blocking flag, or a date that is
not the day it was written for) raises :class:`PersonaSeedError`: the persona is part of the build,
so a drift fails loudly instead of opening a half-filled journal.
"""

from __future__ import annotations

import datetime as dt
import functools
import json
from importlib.resources import files
from typing import Literal

import pydantic
from pydantic import ConfigDict, Field

from daypart.checkin import service
from daypart.checkin.journal import Journal, JournalStore

PERSONA_ID = "persona-v1"
PERSONA_FILE = "persona_v1.json"


class PersonaCheckin(pydantic.BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    day: dt.date
    text: str = Field(min_length=1, max_length=service.MAX_TEXT_CHARS)


class Persona(pydantic.BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    persona_id: str
    display_name: str
    fictional: Literal[True]
    note: str
    member_id: str = Field(pattern=r"^syn-\d{3}$")
    generator: str
    seed: int
    checkins: tuple[PersonaCheckin, ...] = Field(min_length=1)


class PersonaSeedError(RuntimeError):
    """The committed persona no longer replays cleanly through the check-in service."""


class UnknownPersona(LookupError):
    status = 404
    body = {"error": "unknown_persona"}


@functools.lru_cache(maxsize=1)
def _load() -> Persona:
    raw = files("daypart.demo").joinpath(PERSONA_FILE).read_text(encoding="utf-8")
    return Persona.model_validate(json.loads(raw))


def load_persona() -> Persona:
    return _load()


def personas() -> list[dict[str, str]]:
    p = load_persona()
    return [{"persona_id": p.persona_id, "display_name": p.display_name}]


async def seed(store: JournalStore, persona_id: object) -> Journal:
    """A new journal for the persona's member with every persona check-in saved, in order."""
    p = load_persona()
    if persona_id != p.persona_id:
        raise UnknownPersona(str(persona_id))
    journal = store.create(p.member_id)
    journal.display_name, journal.persona_id = p.display_name, p.persona_id
    try:
        for c in p.checkins:
            out = service.create_checkin(journal, text=c.text)
            if out.get("status") != "pending_review":
                raise PersonaSeedError(f"{c.day}: check-in was not a pending review")
            proposals = out["proposals"]
            if any(pr["blocking"] or pr["date"] != c.day.isoformat() for pr in proposals):
                raise PersonaSeedError(f"{c.day}: a proposal is flagged or dated for another day")
            store.register_checkin(out["checkin_id"], journal)
            decisions = [{"proposal_id": pr["proposal_id"], "action": "confirm"} for pr in proposals]
            await service.review(journal, out["checkin_id"], decisions)
    except service.CheckinError as e:
        store.discard(journal)
        raise PersonaSeedError(f"persona check-in refused: {e.body.get('error')}") from None
    except PersonaSeedError:
        store.discard(journal)
        raise
    return journal


__all__ = ["PERSONA_ID", "Persona", "PersonaCheckin", "PersonaSeedError", "UnknownPersona", "load_persona",
           "personas", "seed"]

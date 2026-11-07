"""R6 — the Health Clone Passport view (A&D §4.4, §4.5; AM-1; build plan task 7, addendum G23).

``health_clone_passport(journal, as_of)`` builds one **observation** card per registry concept and
one **pattern** card per existing LHM :class:`~daypart.passport.models.Flag` (I6 path unchanged).

An observation card shows a *recorded* value, never a computed one: the latest confirmed, mapped
value saved in this journal (``origin="observed"``), else the latest point of the simulated cohort
series for that concept (``origin="simulated"``). It is ready iff that value is at most
:data:`READY_WINDOW_DAYS` days old at ``as_of``; a withheld card carries no number. A sourced
``reference_range`` (AM-1) sits beside a ready value with its population and source link, and
nothing judges the value against it (A2). ``plausible`` bounds never appear here.

Every card has an :class:`EvidenceThread` of exactly five steps. A step with nothing behind it
still renders, with ``label="none"``, a ``#passport/why-empty/<step>`` link and a note.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any, Literal

import pydantic
from pydantic import ConfigDict, Field, model_validator
from syntropy.lhm.metrics.claims import assert_narration_safe

from daypart.checkin.journal import Journal, ObservationRecord
from daypart.demo.safety import safe_text
from daypart.evidence.registry import EvidenceRegistry, Source, load_evidence
from daypart.membrane import dsl
from daypart.memory.events import SignalEvent
from daypart.memory.lhm import SERIES_NODES
from daypart.memory.registry import REVIEWER_STATUS, Concept, ConceptRegistry, load_registry
from daypart.passport.constants import WITHHELD_MESSAGE
from daypart.passport.models import Flag
from daypart.passport.render import flags_from_state
from daypart.simmember.trajectory import START_DATE

DISPLAY_NAME = "Health Clone Passport"
NOT_ENOUGH_EVIDENCE = "Not enough evidence"
READY_WINDOW_DAYS = 14
STEP_NAMES: tuple[str, ...] = ("source", "observation", "memory", "explanation", "evaluation")
TEMPLATE_ID = "why-tracked-v1"
_TEMPLATE = "Why this is tracked: {supports}"
SIMULATED_METHOD = "simulated-series-v1"
PATTERN_UNIT = "{score}"

VERTICAL_LABELS: Mapping[str, str] = {
    "vitals_body": "Vitals and body measures",
    "behaviour_function": "Behaviour and function",
    "symptoms_wellbeing": "Symptoms and wellbeing",
}
# Registry gap ids → labels that pass the narration guard ("preventive" is a banned term, D11).
GAP_LABELS: Mapping[str, str] = {
    "labs": "Lab results",
    "conditions": "Conditions",
    "medications": "Medications",
    "care history": "Care history",
    "preventive care": "Screenings and check-ups",
}
_SOURCE_LABELS = {"text": "Your text check-in", "file_fixture": "Demo fixture file", "image_fixture": "Demo fixture image"}
_SIMULATED_SOURCE = "Simulated cohort series"
_NO_SOURCE = "No record yet"
_OBSERVED_LIMIT = "Self-reported in this demo journal; not checked against a device or a record."
_SIMULATED_LIMIT = "Simulated outcomes are not patient outcomes."
_DEMO_LIMIT = "Demo data only: a synthetic member, not a patient record."
_PATTERN_LIMIT = "A pattern score comes from simulated cohort data and this journal."
_WHY_EMPTY = {
    "source": "nothing has been recorded for this measure yet",
    "observation": "no saved or simulated value exists for this measure yet",
    "explanation": "no evidence source covers this measure yet",
    "evaluation": "no explanation was checked, so there is no membrane verdict",
    "evaluation_run": "no boundary evaluation run is recorded in the learning lab",
}


def _why_empty(step: str) -> str:
    return f"#passport/why-empty/{step}"


def _narration_safe(what: str, text: str) -> None:
    try:
        assert_narration_safe(text)
    except Exception as exc:  # fail closed, as Flag does
        raise ValueError(f"{what} fails the narration guard (D11): {exc}") from None


# --- models -------------------------------------------------------------------------------------


class _Step(pydantic.BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str = Field(min_length=1)
    link: str = Field(min_length=1)
    note: str | None = None

    @model_validator(mode="after")
    def _empty_step(self) -> _Step:
        step = getattr(self, "step")
        if self.label == "none" and (self.link != _why_empty(step) or not self.note):
            raise ValueError(f"an empty {step} step links {_why_empty(step)!r} and says why")
        return self


class SourceStep(_Step):
    step: Literal["source"] = "source"
    ref: str | None


class ObservationStep(_Step):
    step: Literal["observation"] = "observation"
    event_id: str | None
    record_id: str | None
    concept_id: str


class MemoryStep(_Step):
    step: Literal["memory"] = "memory"
    ontology_version: str
    readiness: Literal["ready", "not_ready"]


class ExplanationStep(_Step):
    step: Literal["explanation"] = "explanation"
    template_id: str | None
    evidence_ids: tuple[str, ...]
    status: Literal["shown", "suppressed"]
    links: tuple[str, ...]


class EvaluationStep(_Step):
    step: Literal["evaluation"] = "evaluation"
    membrane_verdict: Literal["pass", "blocked", "not_run"]
    rule_version: str
    run_id: str | None


class EvidenceThread(pydantic.BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    steps: tuple[SourceStep, ObservationStep, MemoryStep, ExplanationStep, EvaluationStep]


class ShownRange(pydantic.BaseModel):
    """A sourced range as rendered: the numbers, its population and where they come from (AM-1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    low: float | None
    high: float | None
    unit: str
    population: str
    source_evidence_id: str
    source_url: str


class Card(pydantic.BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    card_id: str
    concept_id: str
    title: str
    kind: Literal["observation", "pattern"]
    origin: Literal["observed", "simulated"]
    status: Literal["ready", "withheld"]
    value: float | None
    unit: str | None
    value_label: str | None  # "You recorded" | "Simulated record" | "Pattern score"; null unless ready
    data_age_days: int | None
    message: str | None
    source: str
    method: str
    limits: tuple[str, ...] = Field(min_length=1)
    reference_range: ShownRange | None
    reference_range_status: Literal["shown", "none", "withheld"]
    explanation: str | None
    explanation_status: Literal["shown", "suppressed"]
    explanation_text: str  # the explanation, or "Not enough evidence"
    thread: EvidenceThread

    @model_validator(mode="after")
    def _check(self) -> Card:
        if self.status == "ready":
            if self.value is None or not math.isfinite(self.value) or self.unit is None:
                raise ValueError("a ready card shows a finite value and its unit")
            if self.value_label is None or self.data_age_days is None or self.message is not None:
                raise ValueError("a ready card has a value label and a data age, and no message")
            if self.reference_range_status == "withheld":
                raise ValueError("a ready card does not withhold its range")
        else:
            numbers = (self.value, self.unit, self.value_label, self.data_age_days, self.reference_range)
            if any(x is not None for x in numbers) or self.explanation is not None:
                raise ValueError("a withheld card never carries a number or an explanation (I6)")
            if self.message != WITHHELD_MESSAGE or self.reference_range_status != "withheld":
                raise ValueError(f"a withheld card says {WITHHELD_MESSAGE!r} and withholds its range")
        if (self.reference_range is not None) != (self.reference_range_status == "shown"):
            raise ValueError("reference_range is set iff reference_range_status is 'shown'")
        if (self.explanation is not None) != (self.explanation_status == "shown"):
            raise ValueError("explanation is set iff explanation_status is 'shown'")
        if self.explanation_text != (self.explanation or NOT_ENOUGH_EVIDENCE):
            raise ValueError("explanation_text is the explanation or 'Not enough evidence'")
        texts = [self.title, self.source, self.method, self.explanation_text, *self.limits]
        texts += [t for t in (self.message, self.value_label) if t is not None]
        for text in texts:
            _narration_safe("card text", text)
        return self


class ConceptRef(pydantic.BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    concept_id: str
    code: str
    display: str


class VerticalView(pydantic.BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    vertical: str
    label: str
    concepts: tuple[ConceptRef, ...]


class Inventory(pydantic.BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    verticals: tuple[VerticalView, ...]
    gaps: tuple[str, ...]  # guard-safe labels (GAP_LABELS); /api/inventory also lists the registry ids

    @model_validator(mode="after")
    def _check(self) -> Inventory:
        for text in (*self.gaps, *(v.label for v in self.verticals)):
            _narration_safe("inventory label", text)
        return self


class HealthClonePassport(pydantic.BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    display_name: Literal["Health Clone Passport"] = DISPLAY_NAME
    journal_id: str
    member_id: str
    as_of: dt.datetime
    ontology_version: str
    loinc_version: str
    guard_versions: Mapping[str, str]
    mode: Literal["demo"] = "demo"
    cards: tuple[Card, ...]
    inventory: Inventory


# --- helpers ------------------------------------------------------------------------------------


def journal_as_of(journal: Journal, day: int | None = None) -> dt.datetime:
    """12:00 UTC on ``START_DATE + day`` (default: the journal's ``today``), the time saved values carry (G9)."""
    date = journal.today if day is None else START_DATE.date() + dt.timedelta(days=day)
    return dt.datetime.combine(date, dt.time(12), tzinfo=dt.timezone.utc)


def journal_day(journal: Journal) -> int:
    """The journal's ``today`` as a day offset from ``START_DATE`` (the largest ``?day=``)."""
    return (journal.today - START_DATE.date()).days


def _results_dir() -> Path:
    from daypart.demo.dashboard_data import default_metrics_path, results_dir

    return results_dir(default_metrics_path())


def boundary_run_id(results: str | os.PathLike[str] | None = None) -> str | None:
    """The DPO boundary-eval run id the learning lab shows (A&D §4.8): ``pipeline.tag/<dpo adapter>``.

    None when ``pipeline.json`` or ``boundary_eval.json`` is missing or lacks the fields.
    """
    d = Path(results) if results is not None else _results_dir()
    try:
        tag = json.loads((d / "pipeline.json").read_text("utf-8"))["tag"]
        dpo = json.loads((d / "boundary_eval.json").read_text("utf-8"))["meta"]["adapters"]["dpo"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not (isinstance(tag, str) and tag and isinstance(dpo, str) and PurePosixPath(dpo).name):
        return None
    return f"{tag}/{PurePosixPath(dpo).name}"


def inventory(registry: ConceptRegistry | None = None) -> Inventory:
    reg = registry if registry is not None else load_registry()
    return Inventory(
        verticals=tuple(
            VerticalView(
                vertical=v,
                label=label,
                concepts=tuple(
                    ConceptRef(concept_id=c.concept_id, code=c.code, display=c.display) for c in reg.by_vertical(v)
                ),
            )
            for v, label in VERTICAL_LABELS.items()
        ),
        gaps=tuple(_gap_label(g) for g in reg.gaps),
    )


def _gap_label(gap: str) -> str:
    label = GAP_LABELS.get(gap, gap)
    return label if safe_text(label) == label else "Not yet covered"


def inventory_view() -> dict[str, Any]:
    """``GET /api/inventory``: the verticals, the gap ids and their labels, the LOINC version and the review label."""
    reg = load_registry()
    inv = inventory(reg).model_dump(mode="json")
    return {
        "verticals": inv["verticals"],
        "gaps": list(reg.gaps),  # the registry ids (T5.4)
        "gap_labels": inv["gaps"],  # what the passport shows for each
        "loinc_version": reg.loinc_version,
        "reviewer_status": REVIEWER_STATUS,
    }


def _age(as_of: dt.datetime, at: dt.datetime) -> int:
    return (as_of.date() - at.astimezone(dt.timezone.utc).date()).days


def _fresh(as_of: dt.datetime, at: dt.datetime | None) -> bool:
    return at is not None and 0 <= _age(as_of, at) <= READY_WINDOW_DAYS


def _latest_records(journal: Journal, as_of: dt.datetime) -> dict[str, ObservationRecord]:
    """concept_id → the latest mapped record at ``as_of`` (a later save wins a same-time tie)."""
    out: dict[str, ObservationRecord] = {}
    for rec in journal.provenance.values():  # insertion order = save order
        if rec.status != "mapped" or rec.concept_id is None or rec.observed_at > as_of:
            continue
        prev = out.get(rec.concept_id)
        if prev is None or rec.observed_at >= prev.observed_at:
            out[rec.concept_id] = rec
    return out


class _Series:
    """The simulated cohort series at ``as_of``: per code, the latest valued point and the latest sample."""

    def __init__(self, records: Sequence[Any], as_of: dt.datetime) -> None:
        self.latest_value: dict[str, tuple[dt.datetime, float]] = {}
        self.latest_sample: dict[str, dt.datetime] = {}
        for rec in records:
            code = SERIES_NODES.get(rec.metric_display)
            if code is None:
                continue
            for p in rec.points:
                if p.observed_at > as_of:
                    continue
                if p.value is not None or p.note is not None:
                    if code not in self.latest_sample or p.observed_at >= self.latest_sample[code]:
                        self.latest_sample[code] = p.observed_at
                if p.value is not None:
                    prev = self.latest_value.get(code)
                    if prev is None or p.observed_at >= prev[0]:
                        self.latest_value[code] = (p.observed_at, float(p.value))


def _source_step(rec: ObservationRecord | None, simulated: bool, seed: int) -> tuple[SourceStep, str, str]:
    """(step, card ``source``, card ``method``)."""
    if rec is not None:
        prov = rec.provenance
        label = _SOURCE_LABELS[prov.source_kind]
        if prov.source_kind == "text":
            step = SourceStep(label=label, ref=prov.checkin_id, link=f"#review/{prov.checkin_id}")
        else:
            step = SourceStep(label=label, ref=prov.source_ref, link=f"/api/fixtures/{prov.source_ref}")
        return step, label, prov.method
    if simulated:
        step = SourceStep(label=_SIMULATED_SOURCE, ref=f"simulated-cohort/seed-{seed}", link="#research")
        return step, _SIMULATED_SOURCE, SIMULATED_METHOD
    step = SourceStep(label="none", ref=None, link=_why_empty("source"), note=_WHY_EMPTY["source"])
    return step, _NO_SOURCE, "none"


def _observation_step(journal: Journal, rec: ObservationRecord | None, simulated: bool, concept_id: str) -> ObservationStep:
    if rec is not None:
        return ObservationStep(
            label="Saved observation",
            event_id=rec.event_id,
            record_id=rec.record_id,
            concept_id=concept_id,
            link=f"/api/journals/{journal.journal_id}/observations/{rec.record_id}",
        )
    if simulated:
        return ObservationStep(label="simulated series", event_id=None, record_id=None, concept_id=concept_id, link="#research")
    return ObservationStep(
        label="none", event_id=None, record_id=None, concept_id=concept_id,
        link=_why_empty("observation"), note=_WHY_EMPTY["observation"],
    )


def _explain(
    sources: tuple[Source, ...], ready: bool, run_id: str | None
) -> tuple[str | None, ExplanationStep, EvaluationStep]:
    """The suppression rule (§4.5): shown iff sourced, ``safe_text`` and ``dsl.check`` pass, and ready."""
    if not sources:
        expl = ExplanationStep(
            label="none", template_id=None, evidence_ids=(), status="suppressed", links=(),
            link=_why_empty("explanation"), note=_WHY_EMPTY["explanation"],
        )
        ev = EvaluationStep(
            label="none", membrane_verdict="not_run", rule_version=dsl.RULE_VERSION, run_id=run_id,
            link=_why_empty("evaluation"), note=_WHY_EMPTY["evaluation"],
        )
        return None, expl, ev
    text = _TEMPLATE.format(supports=sources[0].supports)
    verdict = dsl.check(text)
    safe = safe_text(text) == text and verdict.passed
    shown = safe and ready
    note = None
    if not safe:
        note = "the explanation failed the safety check, so it is not shown"
    elif not ready:
        note = "the value is withheld, so its explanation is not shown"
    expl = ExplanationStep(
        label=sources[0].title,
        template_id=TEMPLATE_ID,
        evidence_ids=tuple(s.evidence_id for s in sources),
        status="shown" if shown else "suppressed",
        link=sources[0].url,
        links=tuple(s.url for s in sources),
        note=note,
    )
    verdict_name: Literal["pass", "blocked"] = "pass" if verdict.passed else "blocked"
    label = f"Membrane check: {verdict_name}"
    if run_id is None:
        ev = EvaluationStep(
            label=label, membrane_verdict=verdict_name, rule_version=verdict.rule_version, run_id=None,
            link=_why_empty("evaluation"), note=_WHY_EMPTY["evaluation_run"],
        )
    else:
        ev = EvaluationStep(
            label=label, membrane_verdict=verdict_name, rule_version=verdict.rule_version, run_id=run_id,
            link=f"#lab/{run_id}",
        )
    return (text if shown else None), expl, ev


def _shown_range(concept: Concept | None, evidence: EvidenceRegistry) -> ShownRange | None:
    rr = concept.reference_range if concept is not None else None
    if rr is None:
        return None
    src = evidence.by_id(rr.source_evidence_id)
    if src is None:  # load_evidence() refuses this; fail closed anyway
        return None
    return ShownRange(
        low=rr.low, high=rr.high, unit=rr.unit, population=rr.population,
        source_evidence_id=rr.source_evidence_id, source_url=src.url,
    )


def _title(journal: Journal, code: str, fallback: str) -> str:
    node = journal.ontology.nodes.get(code)
    text = (node.label or node.display) if node is not None else fallback
    return text if text and safe_text(text) == text else fallback


def _card(
    *,
    card_id: str,
    concept_id: str,
    title: str,
    kind: Literal["observation", "pattern"],
    origin: Literal["observed", "simulated"],
    ready: bool,
    value: float | None,
    unit: str | None,
    value_label: str,
    age: int | None,
    source: str,
    method: str,
    limits: tuple[str, ...],
    shown_range: ShownRange | None,
    sources: tuple[Source, ...],
    run_id: str | None,
    ontology_version: str,
    source_step: SourceStep,
    observation_step: ObservationStep,
) -> Card:
    explanation, expl_step, eval_step = _explain(sources, ready, run_id)
    memory = MemoryStep(
        label=f"Memory {ontology_version}", ontology_version=ontology_version,
        readiness="ready" if ready else "not_ready", link="#passport/inventory",
    )
    return Card(
        card_id=card_id,
        concept_id=concept_id,
        title=title,
        kind=kind,
        origin=origin,
        status="ready" if ready else "withheld",
        value=value if ready else None,
        unit=unit if ready else None,
        value_label=value_label if ready else None,
        data_age_days=age if ready else None,
        message=None if ready else WITHHELD_MESSAGE,
        source=source,
        method=method,
        limits=limits,
        reference_range=shown_range if ready else None,
        reference_range_status=("shown" if shown_range is not None else "none") if ready else "withheld",
        explanation=explanation,
        explanation_status="shown" if explanation is not None else "suppressed",
        explanation_text=explanation or NOT_ENOUGH_EVIDENCE,
        thread=EvidenceThread(steps=(source_step, observation_step, memory, expl_step, eval_step)),
    )


# --- the view -----------------------------------------------------------------------------------


async def health_clone_passport(journal: Journal, as_of: dt.datetime) -> HealthClonePassport:
    """The journal's passport at ``as_of``: observation cards (registry order), then pattern cards."""
    reg = load_registry()
    evidence = load_evidence()
    member_id = journal.member.member_id
    seed = journal.cohort_seed
    state = await journal.memory.metric_state(member_id, as_of)
    series = _Series(await journal.memory.adapter.read_outcome_series(member_id), as_of)
    records = _latest_records(journal, as_of)
    run_id = boundary_run_id()
    ontology_version = state.ontology_version

    cards: list[Card] = []
    for c in reg.concepts():
        rec = records.get(c.concept_id)
        sim = series.latest_value.get(c.code)
        simulated = rec is None and sim is not None
        if rec is not None:
            at, value, unit, label = rec.observed_at, rec.value, rec.unit, "You recorded"
            limits = (_OBSERVED_LIMIT, c.allowed_use, _DEMO_LIMIT)
        elif sim is not None:
            at, value, unit, label = sim[0], sim[1], c.unit, "Simulated record"
            limits = (_SIMULATED_LIMIT, c.allowed_use, _DEMO_LIMIT)
        else:
            at, value, unit, label = None, None, None, "You recorded"
            limits = (_DEMO_LIMIT,)
        ready = _fresh(as_of, at) and value is not None and unit is not None
        source_step, source, method = _source_step(rec, simulated, seed)
        cards.append(
            _card(
                card_id=f"observation:{c.concept_id}",
                concept_id=c.concept_id,
                title=_title(journal, c.code, c.display),
                kind="observation",
                origin="observed" if rec is not None else "simulated",  # observed = saved in this journal
                ready=ready,
                value=value,
                unit=unit,
                value_label=label,
                age=_age(as_of, at) if at is not None else None,
                source=source,
                method=method,
                limits=limits,
                shown_range=_shown_range(c, evidence),
                sources=evidence.for_concept(c.concept_id),
                run_id=run_id,
                ontology_version=ontology_version,
                source_step=source_step,
                observation_step=_observation_step(journal, rec, simulated, c.concept_id),
            )
        )

    events = [e for e in journal.events.events(member_id, as_of=as_of) if isinstance(e, SignalEvent)]
    by_event = {r.event_id: r for r in journal.provenance.values() if r.event_id is not None}
    for flag in flags_from_state(state, journal.ontology):
        cards.append(_pattern_card(journal, flag, reg, evidence, events, by_event, series, as_of, seed, run_id, ontology_version))

    return HealthClonePassport(
        journal_id=journal.journal_id,
        member_id=member_id,
        as_of=as_of,
        ontology_version=ontology_version,
        loinc_version=reg.loinc_version,
        guard_versions=dict(state.guard_versions),
        cards=tuple(cards),
        inventory=inventory(reg),
    )


def _pattern_card(
    journal: Journal,
    flag: Flag,
    reg: ConceptRegistry,
    evidence: EvidenceRegistry,
    events: Sequence[SignalEvent],
    by_event: Mapping[str, ObservationRecord],
    series: _Series,
    as_of: dt.datetime,
    seed: int,
    run_id: str | None,
    ontology_version: str,
) -> Card:
    """An existing LHM ``Flag`` as a card: readiness, value and caveats come from the flag unchanged (I6)."""
    concept = reg.by_code(flag.code)
    concept_id = concept.concept_id if concept is not None else flag.code
    own = [e for e in events if e.code == flag.code]
    latest_event = max(own, key=lambda e: e.occurred_at) if own else None
    rec = by_event.get(latest_event.event_id) if latest_event is not None else None
    simulated = flag.code in series.latest_sample
    samples = [t for t in (series.latest_sample.get(flag.code), latest_event.occurred_at if latest_event else None) if t]
    at = max(samples) if samples else None
    ready = flag.status == "ready"
    source_step, _, _ = _source_step(rec, simulated and rec is None, seed)
    from_journal = rec is not None
    source = "Pattern score from simulated cohort data" + (" and this journal" if from_journal else "")
    return _card(
        card_id=f"pattern:{flag.code}",
        concept_id=concept_id,
        title=flag.title,
        kind="pattern",
        origin="observed" if from_journal else "simulated",
        ready=ready and at is not None,
        value=flag.value,
        unit=PATTERN_UNIT,
        value_label="Pattern score",
        age=_age(as_of, at) if at is not None else None,
        source=source,
        method=f"lhm-domain:{flag.lhm_domain}",
        limits=(*flag.caveats, _PATTERN_LIMIT),
        shown_range=None,
        sources=evidence.for_concept(concept_id) if concept is not None else (),
        run_id=run_id,
        ontology_version=ontology_version,
        source_step=source_step,
        observation_step=_observation_step(journal, rec, simulated and rec is None, concept_id),
    )


__all__ = [
    "DISPLAY_NAME",
    "GAP_LABELS",
    "NOT_ENOUGH_EVIDENCE",
    "READY_WINDOW_DAYS",
    "STEP_NAMES",
    "TEMPLATE_ID",
    "Card",
    "EvidenceThread",
    "HealthClonePassport",
    "Inventory",
    "ShownRange",
    "boundary_run_id",
    "health_clone_passport",
    "inventory",
    "inventory_view",
    "journal_as_of",
    "journal_day",
]

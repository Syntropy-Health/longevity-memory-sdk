# Hosted build probe, 2026-11-10

A committed record of what the hosted prototype did when agents tested it as a judge would, so
that the [form responses](../form-responses.md), the [deck outline](../deck-outline.md) and the
[technical appendix](../technical-appendix.md) describe only behaviour the hosted build showed.

- **Host:** https://supermomo668--daypart-demo-playground.us-east.modal.run (member app at `/`,
  research console at `/admin`).
- **Build:** `daypart/build` @ `68236f1d2c84ac4e41f12674602f5686a9e3979e`, deployed by the CI
  workflow `.github/workflows/engine.yml`, run **42873055419** (success, 2026-11-10 18:13 UTC).
  Every gate job (tests, type check, browser and accessibility suite, attribution boundary) passed
  before the deploy job ran.
- **Probed:** 2026-11-10, 18:30 to 18:40 UTC. Every input was synthetic. Journal ids are
  per-visitor and in memory, so they are shortened here; a fresh run gets new ones.

## 1. SC1 journey smoke: 9 of 9 steps passed

`engine/tools/smoke_journey.py` (the same script the deploy job runs), from `engine/`:

```text
ok  create journal: 201
ok  next step before any save: 409
ok  text check-in: 201
ok  review, confirm all: 200
ok  passport: 200
ok  next step: 200
ok  choose next step: 200
ok  lab: 200
ok  real-input mode refused: 403
SC1 journey ok
```

## 2. Check-in extraction on a four-part sentence

`POST /api/checkins` with `{"journal_id": …, "text": "slept 6 hours, pain 4/10, mood 3 out of 5,
walked 8000 steps"}` returned **201, `pending_review`, 3 proposals** (nothing saved yet):

| proposal | concept | value | unit | snippet | method | confidence |
|---|---|---|---|---|---|---|
| p-1 | 93832-4 Sleep duration | 6.0 | h | "slept 6 hours" | rules-v1 | high |
| p-2 | 72514-3 Pain severity 0-10 | 4.0 | {score} | "pain 4/10" | rules-v1 | high |
| p-3 | 55423-8 Number of steps | 8000.0 | {steps} | "walked 8000 steps" | rules-v1 | high |

The phrase "mood 3 out of 5" produced **no proposal**: the text rules do not read it. This is a
coverage gap of the deterministic rules, not a refusal.

`"felt a bit odd today"` returned **422** `{"error": "nothing_extracted", "hint": "try e.g. 'slept 7 hours'"}`.

## 3. Blocked and abstained cases

**Crisis language: answered with a fixed hand-off, nothing extracted.**

```json
POST /api/checkins {"journal_id": "…", "text": "I want to end my life"}
200 {"status": "handoff", "text": "If anything about your routine feels off, your care team is glad to talk it through with you. If you might be in danger or thinking about harming yourself, contact your local emergency services now."}
```

**Text that looks like personal data: refused whole.**

```json
POST /api/checkins {"journal_id": "…", "text": "my name is Jane, email jane at example dot com, slept 7 hours"}
422 {"error": "looks_like_personal_data", "reasons": ["email", "self_name"], "warning": "Do not enter real health data."}
```

(The probe sent a literal e-mail address; it is spelled out here.)

**Real input: refused by the build.**

```json
POST /api/mode {"real_input": true}
403 {"error": "real_input_refused", "reason": "build_disallowed", "open_gates": [12 gates, every owner "unassigned"]}
```

The 12 gates: lawful basis, consent, access control, encryption, retention and deletion, audit,
incident response, processor terms, jurisdiction review, clinical intended use, qualified
oversight, regulatory review.

## 4. The prepared fictional member's passport

`POST /api/journals {"persona": "persona-v1"}` returned 201: Rowan Ellis (synthetic member
`syn-007`), 28 saved check-ins, journal "today" 2026-09-29.

`GET /api/journals/{id}/passport` returned **200** with 24 cards, ontology `core-v1+u1`, LOINC 2.83:

| origin | ready | withheld | total |
|---|---|---|---|
| observed (the member's own saved values) | 7 | 1 | 8 |
| simulated (synthetic cohort or pattern) | 2 | 14 | 16 |
| **total** | **9** | **15** | **24** |

- 4 of the 24 cards show a sourced reference range beside the value: heart rate 63 /min (60 to
  100, MedlinePlus), systolic 123 and diastolic 79 mm[Hg] (MedlinePlus), sleep 7.5 h (7 to 9,
  NHLBI). No card says high, low or abnormal.
- Every withheld card shows "Not enough data yet." and no number.
- The **pain rating** card is observed but withheld: its last saved value is from 2026-09-13,
  16 days before the journal's today, past the 14-day readiness limit. Its explanation reads
  "Not enough evidence" (`explanation_status: suppressed`).
- A ready card's evidence thread has 5 steps: the check-in that sourced it, the saved observation
  (`/api/journals/{id}/observations/obs-86`), memory `core-v1+u1`, the explanation and its public
  source, and the membrane check `pass` (`boundary-v1`).
- The inventory lists 5 gaps: lab results, conditions, medications, care history, screenings and
  check-ups.

`GET /api/journals/{id}/timeline` returned 200 with 28 entries (`timeline-v1`, `omitted: 0`),
one per saved check-in, each with its appended observations and the passport changes it caused.

`GET /api/journals/{id}/next-step` returned 200:
`{"intent": "check_in_question", "text": "How are you feeling about your routine this week?",
"membrane": {"decision": "pass", "rule_hits": []}, "options": ["choose", "defer",
"ask_professional"], "replaced": false}`.

## 5. Other read-only routes

- `GET /api/fixtures`: 4 bundled synthetic files, 2 photos (blood pressure monitor, bathroom
  scale) and 2 device files, labelled "Device file: symptom diary (JSON)" and "Device file: 3-day wearable
  export (CSV)". Both are synthetic files from a committed generator. No wearable, device, sensor or
  account is connected; only these 4 files are accepted, by sha256.
- `GET /api/lab`: 7 rows: base, SFT and DPO, 3 scripted simulator baselines and GRPO "proposed,
  not built". The same numbers as [outcomes.md](../outcomes.md).
- `GET /api/health`: `{"status": "ok", "cohort_seed": 0}`.

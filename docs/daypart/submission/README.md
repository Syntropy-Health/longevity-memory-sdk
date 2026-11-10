# Clinical Human Clone & Health Clone Passport: FHDIC submission pack

A prototype for the Future Health Digital Innovation Challenge (FHDIC). A judge checks in about a
synthetic member's day, reviews what the system understood, and saves only what they confirm.
The confirmed values become a **Health Clone Passport** with an evidence thread on every card, a
**suggested next step** the person can choose, defer or hand to a professional, and a **learning
lab** that shows only committed training and evaluation results, each with its run ID.

Agents prepared this pack. The principal submits it; agents submit nothing.

**Data.** The app opens on a prepared member, Rowan Ellis, a fictional person with 28 days of
check-ins already saved through the same review step a person uses. Every member, value and result
is synthetic, and the prototype gives no diagnosis, treatment or dosing advice
([assumptions and limits](assumptions-limits.md)). Real-input mode is a gate that always refuses
([real-input pathway](real-input-pathway.md)).

## The pack

| File | What it holds |
|---|---|
| [README.md](README.md) | This index: demo URLs, the judge's path and the challenge framing |
| [architecture.md](architecture.md) | The system diagrams, components, API and CI gates (technical documentation) |
| [evidence-ledger.md](evidence-ledger.md) | Every claim in the pack, traced to a committed file or marked as an assumption |
| [outcomes.md](outcomes.md) | The learning-lab results, generated from the committed results, never typed by hand |
| [assumptions-limits.md](assumptions-limits.md) | Assumptions, dependencies and limitations |
| [organiser-rules.md](organiser-rules.md) | The organiser's published rules, checked, with the cutoff |
| [real-input-pathway.md](real-input-pathway.md) | Why real input is off and what would have to change |
| [form-responses.md](form-responses.md) | Draft answers for each submission-form field, with character counts against the limits |
| [deck-outline.md](deck-outline.md) | The 8-slide deck outline: one message, ledger rows and illustration per slide |
| [technical-appendix.md](technical-appendix.md) | Technical and responsible-AI appendix: mechanisms, training, rigour, safety, data rights, validation path |
| [sources/hosted-probe-2026-11-10.md](sources/hosted-probe-2026-11-10.md) | What the hosted build at 68236f1 did when tested as a judge would |

## Demo

| Surface | URL |
|---|---|
| **Clinical Human Clone**, member app (the four-screen journey) | https://supermomo668--daypart-demo-playground.us-east.modal.run |
| Research console (learning lab, concept inventory, research playground) | https://supermomo668--daypart-demo-playground.us-east.modal.run/admin |
| API explorer (OpenAPI) | https://supermomo668--daypart-demo-playground.us-east.modal.run/docs |
| Research view: full results (dashboard) | https://supermomo668--daypart-demo-dashboard.us-east.modal.run |

Source: https://github.com/Syntropy-Health/longevity-memory-sdk (the engine is in `engine/`). CI
redeploys both apps from `.github/workflows/engine.yml` after every green push to the staging branch
(`daypart/build`) or `main` that changes the engine, these docs or the workflow.

### What a judge clicks

The member app and the research console are separate: the member app never links into the console.

1. **Check in** ("What matters today?"): type a sentence such as "slept 6 hours and walked 8000
   steps", or import one of the supported device files or photos. Voice and video show as
   unavailable. "Start a fresh journal" swaps the prepared member for an empty journal.
2. **Review before saving**: one row per value the system found, with the source snippet, the
   method, the value, unit and date, and any flags. Confirm, correct, discard or save as unmapped.
   Nothing is saved until you submit the review.
3. **Health Clone Passport**: a card per concept, marked observed or simulated, with its data age,
   source and limits. A sourced reference range sits beside a ready value with its population and
   source link; nothing is marked high or low. Open **Evidence thread** on any card. Cards without
   enough evidence say so instead of showing a number. **Inclinations** lists what weighs most on
   keeping the routine and up to three next steps, each linked to it with its reason (simulated
   members only; [technical appendix §4a](technical-appendix.md#4a-inclinations-question-library-reward-model-and-grpo)).
4. **Suggested next step**: a plain-language suggestion and its reason. Choose it, defer it, or
   ask a professional.
5. **Learning lab** (research console, `/admin`): the base, SFT and DPO results and three scripted
   baselines, each with its run ID, split, seed and failure count, and the GRPO policy measured on the same scenarios (simulated).
   The same table is in [outcomes.md](outcomes.md).

On the research console, the footer's **Real input** control asks the server to turn real input on.
The server refuses and lists the open gates. The old episode playground is there as "Research
playground", and the concept inventory lists every concept the clone can record.

The whole journey works with a keyboard alone, at 375 px wide, and with reduced motion. CI runs
axe on every screen before each deploy.

## Challenge framing

The page does not number its challenges; the numbers below are their positions in the organiser's
list ([organiser research](sources/organiser-research-2026-11-06.md)).

- **Primary: #9 Sustaining Healthy Behaviors.** The next step is chosen by the person, never
  imposed. A lapse is met with problem-solving, not a reset. Each suggestion shows its reason and
  limits, and the person stays in control of what is saved.
- **Supporting: #4 Precision Prevention and Screening.** The passport makes uncertainty and data
  provenance visible: observed or simulated, data age, source, method, and an explicit gap
  inventory for what the clone does not cover.
- **Supporting: #5 Closing the Screening-to-Care Loop.** "Ask a professional" is always an option,
  and a crisis message is routed to a fixed hand-off instead of being processed. This is a pointer,
  not a care pathway: the prototype has no case ownership or closure.

The board chose this framing (assumption A1, confirmed 2026-11-07). The pack claims only what the
demo shows.

## LOINC

This material contains content from LOINC® (https://loinc.org). LOINC is copyright © 1995-2026, Regenstrief Institute, Inc. and the Logical Observation Identifiers Names and Codes (LOINC) Committee and is available at no cost under the license at https://loinc.org/license/. LOINC® is a registered United States trademark of Regenstrief Institute, Inc.

The codes are used to label synthetic values only, with no clinical interpretation. LOINC 2.83,
18 codes. Licence: https://loinc.org/license/. Every third-party component is listed in
[ATTRIBUTION.md](../../../ATTRIBUTION.md).

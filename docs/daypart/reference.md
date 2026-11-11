# Clinical Human Clone & Health Clone Passport: reference

The reference for the completed FHDIC build (HAC-38,
plan `workstreams/daypart/plan/BUILD-PLAN-fhdic.md`, phases P1–P4). It says what the system is,
how it is built, which decisions shaped it, how to use it and what it does not do. The judges'
entry point is the [submission pack](submission/README.md); this page is for the team that
maintains the system.

## Overview

Clinical Human Clone is a longitudinal health journal that explains its own reasoning, run on
synthetic data only. A person checks in with text or a bundled demo file, reviews what the system
extracted, and saves only what they confirm. Confirmed values become LOINC-informed observations.
The **Health Clone Passport** shows each concept with its source, time, provenance,
observed-or-simulated status and a five-step evidence thread (source → observation → memory →
explanation → evaluation). A **suggested next step** can be chosen, deferred or handed to a
professional. The **learning lab** shows only committed training and evaluation results, each
with its run ID.

Demo mode is the only mode. Real-input mode is designed and always refused
([real-input pathway](real-input-pathway.md)). The prototype gives no diagnosis, treatment or
dosing advice.

Live demo: https://supermomo668--daypart-demo-playground.us-east.modal.run (research dashboard:
https://supermomo668--daypart-demo-dashboard.us-east.modal.run).

## Requirements delivered (PVR rev 2, HAC-30)

Every requirement is built; none was descoped. The success criteria SC1–SC9 are checked in the L2
delivery review.

| Req | What shipped | Phase |
|---|---|---|
| R1 Renamed, honest surfaces | "Clinical Human Clone" UI and API titles, demo banner, research view | P3 |
| R2 Text check-in | Rules extractor (`rules-v1`), PII tripwire, crisis pre-check | P1 |
| R3 File and image check-in | 4 allow-listed synthetic fixtures with sidecars; any other file refused | P1 |
| R4 Review before saving | All-or-nothing review; nothing reaches memory before it | P1 |
| R5 LOINC observation registry | 18 LOINC 2.83 + 2 local concepts, `core-v1+u1` | P1 |
| R6 Passport with evidence thread | 20 observation cards + pattern cards, 5-step thread, sourced ranges only | P2, P3 |
| R7 Suggested next step | `next-step-v1` rules, guarded text, choose / defer / ask a professional | P2, P3 |
| R8 Learning lab | Rows from committed results, each with run ID, split, seed and failures | P2, P3 |
| R9 Real-input gate | Designed with 12 gates; always refused | P1 |
| R10 Accessible UI | axe 0 serious/critical, keyboard journey, 375 px, in CI (`demo-ui`) | P3 |
| R11 Submission pack | 7 files in `submission/`, test-checked ledger and generated outcomes | P4 |

## Architecture

The detailed diagrams, components, API table and CI gates are in
[submission/architecture.md](submission/architecture.md); the authoritative contract is the A&D,
`workstreams/daypart/AND.md`, as amended by `workstreams/daypart/plan/ADDENDUM-fhdic.md`
(G13–G30). In short, all under `engine/daypart/`:

| Layer | Module | Role |
|---|---|---|
| Registry | `memory/registry.py`, `registry_a4.json`, `loinc_verify_v1.csv` | 18 LOINC 2.83 codes + 2 local codes (`slice_ontology()` = `core-v1+u1`) |
| Gate | `governance/real_input.py`, `real_input.yaml` | `REAL_INPUT_BUILD_ALLOWED = False`; `POST /api/mode` always 403 with the 12 open gates |
| Check-in | `checkin/` (tripwire, crisis, extractors, fixtures, journal, service, next_step) | Proposals → review → EventLog; nothing is saved before review |
| Evidence | `evidence/registry.py`, `sources_v1.json` | 5 public sources; 7 sourced reference ranges, each matched to its source sentence |
| Passport | `passport/view.py` | Cards, evidence thread, suppression ("Not enough evidence") |
| Lab | `demo/lab.py`, `tools/render_outcomes.py` | Rows from `docs/daypart/results/`; `outcomes.md` is generated |
| UI | `demo/static/index.html`, `demo/app.py` | Hash-route journey `#checkin` → `#review` → `#passport` → `#next` → `#lab`, plus `#research` |

CI (`.github/workflows/engine.yml`): `test`, `typecheck` (pyright basic), `demo-ui` (Playwright
+ axe in headless Chromium) and `attribution-boundary` gate `deploy-demo`, which redeploys both
Modal apps.

## Key decisions

| Decision | Why |
|---|---|
| D-A2: rules + fixture-sidecar extractors, no live model | Deterministic and reviewable for a two-week build; any future model extractor must return the same `Proposal` schema through structured output and `model_validate` (G21) |
| D-A3: in-memory journals, `max_containers=1` | No persistence of member data in a public demo |
| D-A5 / G3: LOINC verified at build through the public HL7 terminology server | 69725-0 failed (a single GAD item, not GAD-2) and was dropped, not replaced |
| AM-1 / G19, G22: sourced reference ranges only | Board answer of 2026-11-07. A range is shown only when a public source states it; nothing is marked high or low |
| G17: flags re-run over the whole set after corrections | Discarding one side of a contradiction must not clear the other |
| G18: crisis check = `boundary-v1` markers + member lexicon | "walked 988 steps" must not trigger it |
| G20: pyright in CI | Board question on typesafe AI (HAC-33) |
| G29: Correct on a flagged proposal sends the shown unit or date | A&D §4.1 clears a flag only when Correct states the value |
| G30: the submission pack is test-checked | Every ledger claim resolves to a committed file or is tagged as an assumption |

## How to use

- **Run locally:** see [docs/usage/daypart.md](../usage/daypart.md) (`daypart-demo serve`,
  `daypart-demo dashboard`).
- **Tests:** from `engine/`, `uv run pytest -q` (unset `MUSE_API_KEY`, or one training test makes
  live calls). The browser suite needs the `ui` group:
  `DAYPART_UI_REQUIRED=1 uv run --group ui pytest -q tests/ui`.
- **Regenerate outcomes:** `uv run python tools/render_outcomes.py` (`--check` in CI and the pack test).
- **Deploy:** push to `daypart/build` or `main`; `deploy-demo` runs after the gates pass.

## Known limitations and future work

- Synthetic data only. Real input stays refused until all 12 gates in `real_input.yaml` close
  and a build sets `REAL_INPUT_BUILD_ALLOWED`; that is a governance decision, not a code change.
- Journals live in memory: they are evicted after 60 minutes idle (the Modal container's
  `scaledown_window` matches it) or beyond 256 journals, and a redeploy clears them. There is no
  per-journal cap on check-ins.
- Ranges exist only for the 7 concepts a fetched public source states (MedlinePlus vital signs,
  NHLBI BMI and sleep). AHA and CDC pages blocked automated fetches, so they are not cited.
- GRPO was "proposed, not built" (out of scope) at this stage. Superseded by HAC-75 (2026-11-10): a small
  GRPO message-type policy, a reward model and the Jev question library are built and run on synthetic
  members only ([technical appendix §4a](submission/technical-appendix.md#4a-inclinations-question-library-reward-model-and-grpo)).
- The Test Author's sealed suite covers P1 only (HAC-39); it passes inside the engine suite at
  plan completion. No sealed P2–P4 suite exists; the unit and browser suites are the evidence there.
- Organiser team registration was confirmed by a board member on 2026-11-09 (HAC-58,
  assumption O5). Eligibility (team size and ages) stays unverified in `organiser-rules.md`.
- `deploy-demo` runs the SC1 API journey on the hosted URL after each deploy
  (`engine/tools/smoke_journey.py`), restarting it with a fresh journal on a deploy rollover (404
  `unknown_journal`/`unknown_checkin` or a network error, up to 5 tries). A failure fails the job
  but does not roll back the deploy.
- Detailed residual risks, per phase and at plan completion: the Known issues blocks in
  [docs/workstreams/daypart.md](../workstreams/daypart.md).

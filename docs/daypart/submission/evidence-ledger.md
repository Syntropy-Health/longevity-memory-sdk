# Evidence and source ledger

Every claim this pack makes, traced to the committed file that shows it, or tagged
`ASSUMPTION <id>` when it rests on an item in [assumptions-limits.md](assumptions-limits.md).
Paths are relative to the repository root, at the commit this pack ships in. Where a test is
listed, it is the check that fails if the claim stops being true.

A unit test (`engine/tests/unit/test_submission_pack_unit.py`, T11.1) fails if any path below
does not exist or any assumption id is not defined.

## The journey (SC1)

| id | claim | evidence |
|---|---|---|
| L1 | The hosted app is the five-screen journey: check in, review, passport, next step, learning lab, plus the optional research view. | `engine/daypart/demo/static/index.html` · `engine/tests/ui/test_journey_a11y.py` |
| L2 | The demo URLs are the existing Modal hosts, redeployed by CI only when every gate job passes. | `.github/workflows/engine.yml` · `engine/deploy/modal_demo.py` |
| L3 | Every screen shows the banner "Demo mode: synthetic inputs and simulated results". | `engine/daypart/demo/static/index.html` · `engine/tests/unit/test_demo_ui_html_unit.py` |
| L4 | The API title is "Clinical Human Clone API"; module and app names are unchanged. | `engine/daypart/demo/app.py` · ASSUMPTION D-A1 |

## Check-in and review (SC9)

| id | claim | evidence |
|---|---|---|
| L5 | Nothing reaches memory before the review; a review is all-or-nothing; a discarded value is never written. | `engine/daypart/checkin/service.py` · `engine/tests/unit/test_checkin_service_unit.py` |
| L6 | Extraction is deterministic rules for text and pre-recorded extractions for 4 synthetic fixtures; no model call at runtime. | `engine/daypart/checkin/extract_text.py` · `engine/daypart/demo/fixtures/manifest.json` · `engine/tests/unit/test_checkin_extract_unit.py` · ASSUMPTION D-A2 |
| L7 | Only the bundled fixtures are accepted, allow-listed by sha256, with a 1 MiB cap; anything else is refused. | `engine/daypart/checkin/fixtures.py` · `engine/tests/unit/test_checkin_fixtures_unit.py` · ASSUMPTION A5 |
| L8 | The fixtures are synthetic and reproducible from a committed generator. | `engine/tools/make_fixtures.py` |
| L9 | Every extractor's output is revalidated as the `Proposal` schema before it reaches the journal; malformed output gets a 500 that repeats no input. | `engine/daypart/checkin/extractor.py` · `engine/tests/unit/test_extractor_contract_unit.py` |
| L10 | Crisis language is checked before extraction, using the `boundary-v1` crisis markers plus a member-language pattern list, and answered with a fixed hand-off. | `engine/daypart/checkin/crisis.py` · `engine/tests/unit/test_checkin_extract_unit.py` |
| L11 | Text that looks like personal data is refused whole; this is defence in depth, not a privacy control. | `engine/daypart/checkin/tripwire.py` · ASSUMPTION D-A7 |
| L12 | Journals are per visitor, in memory only, evicted after 60 minutes idle or beyond 256 journals, in a single container. | `engine/daypart/checkin/journal.py` · `engine/deploy/modal_demo.py` · ASSUMPTION D-A3 |

## Registry and evidence (SC2, SC3)

| id | claim | evidence |
|---|---|---|
| L13 | The registry holds 20 concepts in 3 verticals: 18 LOINC codes and 2 local codes. | `engine/daypart/memory/registry_a4.json` · `engine/tests/unit/test_registry_unit.py` |
| L14 | Every LOINC code was verified against LOINC 2.83; 69725-0 failed and was dropped, not replaced. | `engine/daypart/memory/loinc_verify_v1.csv` · `engine/daypart/memory/registry_a4.json` · `workstreams/daypart/plan/BUILD-PLAN-fhdic.md` · ASSUMPTION D-A5 |
| L15 | The ontology `core-v1+u1` adds the 11 LOINC codes not in `core-v1` through the append-only update; `core-v1` is unchanged. | `engine/daypart/memory/registry.py` · `engine/tests/unit/test_registry_unit.py` |
| L16 | LOINC is used under its licence; the notice is in ATTRIBUTION, the UI footer and this pack's README. | `ATTRIBUTION.md` · `engine/daypart/memory/registry.py` · `engine/tests/unit/test_registry_unit.py` |
| L17 | The evidence registry holds 5 public NIH, MedlinePlus and WHO pages. | `engine/daypart/evidence/sources_v1.json` · `engine/tests/unit/test_evidence_unit.py` |
| L18 | 7 concepts carry a reference range, each copied from a sentence on its source page; the loader refuses a range that does not match. Every other concept has none. | `engine/daypart/memory/registry_a4.json` · `engine/daypart/evidence/registry.py` · `engine/daypart/evidence/sources_v1.json` · `engine/tests/unit/test_evidence_unit.py` |
| L19 | Content is labelled "reviewed: board sign-off 2026-11-07"; no clinician reviewed it. | `engine/daypart/memory/registry_a4.json` · `workstreams/daypart/AND.md` · ASSUMPTION A3 |
| L20 | A reference range is shown beside a value and never interpreted: nothing is marked high, low or abnormal. | `engine/daypart/passport/view.py` · `engine/tests/unit/test_passport_view_unit.py` · ASSUMPTION A2 |

## Passport and next step (SC2)

| id | claim | evidence |
|---|---|---|
| L21 | Every passport card has a 5-step evidence thread, its source, time and provenance, and observed or simulated status. | `engine/daypart/passport/view.py` · `engine/tests/unit/test_passport_view_unit.py` |
| L22 | A card is ready only if its value is at most 14 days old; otherwise it is withheld and carries no number. | `engine/daypart/passport/view.py` · `engine/tests/unit/test_passport_view_unit.py` |
| L23 | A confirmed value is shown exactly as recorded, never as a score. | `engine/daypart/passport/view.py` · ASSUMPTION D-A9 |
| L24 | The next step follows fixed rules, passes the `boundary-v1` membrane, and is replaced by a clinician hand-off if it fails; the person can choose, defer or ask a professional. | `engine/daypart/checkin/next_step.py` · `engine/tests/unit/test_next_step_unit.py` |

## Learning lab (SC4, SC5)

| id | claim | evidence |
|---|---|---|
| L25 | Every learning-lab number is computed from the committed results, with its run ID, split, seed and failure count; a missing field reads "not recorded". | `engine/daypart/demo/lab.py` · `docs/daypart/results/boundary_eval.json` · `docs/daypart/results/training.json` · `docs/daypart/results/metrics.json` · `docs/daypart/results/pipeline.json` · `engine/tests/unit/test_lab_unit.py` |
| L26 | `outcomes.md` is generated from the same table and checked byte for byte. | `engine/tools/render_outcomes.py` · `docs/daypart/submission/outcomes.md` · `engine/tests/unit/test_submission_pack_unit.py` |
| L27 | GRPO is proposed, not built. | `docs/daypart/results/metrics.json` · ASSUMPTION A9 |
| L28 | The curated-25 held-out profiles are in no training artefact (I1), checked in CI. | `engine/daypart/ci/i1_check.py` · `.github/workflows/engine.yml` |
| L29 | The results come from a synthetic simulator and a held-out prompt set, not from people. | `docs/daypart/results/metrics.json` · ASSUMPTION A2 |

## Accessibility and quality (SC6)

| id | claim | evidence |
|---|---|---|
| L30 | axe finds no serious or critical violations of the WCAG 2.0/2.1 A and AA rules on any screen (SC6); the journey completes with a keyboard alone; 375 px shows no horizontal scroll; reduced motion is honoured. | `engine/tests/ui/test_journey_a11y.py` · `.github/workflows/engine.yml` |
| L31 | axe-core is a vendored, sha-pinned copy used only in tests, never served. | `engine/tests/ui/vendor/axe.min.js` · `ATTRIBUTION.md` |
| L32 | Pyright runs over `engine/daypart` and gates the deploy. | `engine/pyproject.toml` · `engine/tests/unit/test_typecheck_ci_unit.py` · `.github/workflows/engine.yml` |

## Real input (SC8)

| id | claim | evidence |
|---|---|---|
| L33 | Real input cannot be enabled from the UI, the API or the environment: the UI and `POST /api/mode` get 403 with the 12 open gates, and `DAYPART_REAL_INPUT=1` is logged and refused at startup. | `engine/daypart/governance/real_input.py` · `engine/daypart/demo/app.py` · `engine/daypart/governance/real_input.yaml` · `engine/tests/unit/test_real_input_unit.py` · ASSUMPTION A6 |
| L34 | The pathway doc's gate table equals the YAML. | `docs/daypart/real-input-pathway.md` · `engine/tests/unit/test_real_input_unit.py` |

## Organiser and framing (SC7)

| id | claim | evidence |
|---|---|---|
| L35 | The submission cutoff is 2026-11-20 18:29 UTC; registration closes 2026-11-10 18:29 UTC. | `docs/daypart/submission/sources/organiser-research-2026-11-06.md` |
| L36 | The organiser asks for a working prototype with technical documentation, assumptions and limitations. | `docs/daypart/submission/sources/organiser-research-2026-11-06.md` |
| L37 | By position in the organiser's list, #9 is Sustaining Healthy Behaviors, #4 Precision Prevention and Screening, #5 Closing the Screening-to-Care Loop. | `docs/daypart/submission/sources/organiser-research-2026-11-06.md` · ASSUMPTION A1 |
| L38 | Synthetic data is acceptable to the organiser. | ASSUMPTION O1 |
| L39 | The hosted prototype, repository and pack cover the requested artefacts. | ASSUMPTION O2 |
| L40 | The repository is licensed Apache-2.0. | `LICENSE` · ASSUMPTION O3 |
| L41 | The framing follows the challenge statements; no judging rubric is published. | `docs/daypart/submission/sources/organiser-research-2026-11-06.md` · ASSUMPTION O4 |
| L42 | The team registered before registration closed on 2026-11-10 18:29 UTC. | `docs/daypart/submission/organiser-rules.md` · ASSUMPTION O5 |

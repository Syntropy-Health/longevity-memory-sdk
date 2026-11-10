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
| L1 | The hosted app has two surfaces: the member app at `/` (check in, review, passport, next step) and the research console at `/admin` (learning lab, concept inventory, research playground). | `engine/daypart/demo/static/index.html` · `engine/daypart/demo/surfaces.py` · `engine/tests/ui/test_journey_a11y.py` |
| L2 | The demo URLs are the existing Modal hosts, redeployed by CI only when every gate job passes. | `.github/workflows/engine.yml` · `engine/deploy/modal_demo.py` |
| L3 | No screen shows a demo banner or a synthetic-data tag; the member app (`/`) and the research console (`/admin`) are separate shells (AM-2). | `engine/daypart/demo/static/index.html` · `engine/daypart/demo/surfaces.py` · `engine/tests/unit/test_demo_ui_html_unit.py` · `engine/tests/unit/test_surfaces_unit.py` |
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

## Submission form, deck and appendix (HAC-64)

The rows below back the [form responses](form-responses.md), the [deck outline](deck-outline.md)
and the [technical appendix](technical-appendix.md). Each quantitative claim carries its
denominator. Claims that rest on an internal report rather than on a test, a run or a committed
result are labelled *reported*.

### The hosted build

| id | claim | evidence |
|---|---|---|
| L43 | The hosted prototype serves `daypart/build` @ 68236f1, deployed by CI run 42873055419 on 2026-11-10 after every gate job passed; agents probed it on 2026-11-10. | `docs/daypart/submission/sources/hosted-probe-2026-11-10.md` · `.github/workflows/engine.yml` |
| L44 | The hosted SC1 smoke passed 9 of 9 steps: journal, next step refused before a save (409), check-in, review, passport (200), next step, choose, lab, real input refused (403). | `engine/tools/smoke_journey.py` · `docs/daypart/submission/sources/hosted-probe-2026-11-10.md` |
| L45 | One four-part sentence gave 3 proposals (sleep, pain, steps), each with its snippet, method and confidence; the fourth part ("mood 3 out of 5") gave none, because the rules do not read it. | `docs/daypart/submission/sources/hosted-probe-2026-11-10.md` · `engine/daypart/checkin/extract_text.py` |
| L46 | A sentence the rules cannot read is answered with 422 "nothing extracted" and saves nothing. | `docs/daypart/submission/sources/hosted-probe-2026-11-10.md` · `engine/tests/unit/test_checkin_extract_unit.py` |
| L47 | A crisis message on the hosted build got the fixed hand-off text (status "handoff") and was not extracted. | `docs/daypart/submission/sources/hosted-probe-2026-11-10.md` · `engine/daypart/checkin/crisis.py` · `engine/tests/unit/test_checkin_extract_unit.py` |
| L48 | Text with an e-mail address and a self-name was refused whole (422, reasons "email" and "self_name"). | `docs/daypart/submission/sources/hosted-probe-2026-11-10.md` · `engine/daypart/checkin/tripwire.py` |
| L49 | The prepared fictional member's passport has 24 cards: 9 ready and 15 withheld; 8 observed (7 ready) and 16 simulated (2 ready). | `docs/daypart/submission/sources/hosted-probe-2026-11-10.md` · `engine/daypart/demo/persona_v1.json` · `engine/daypart/passport/view.py` |
| L50 | 4 of those 24 cards show a sourced reference range beside the value; none is marked high, low or abnormal. | `docs/daypart/submission/sources/hosted-probe-2026-11-10.md` · `engine/daypart/evidence/sources_v1.json` · `engine/tests/unit/test_passport_view_unit.py` |
| L51 | An observed value older than 14 days is withheld: the pain card's last value is 16 days old, so it shows no number and its explanation is suppressed. | `docs/daypart/submission/sources/hosted-probe-2026-11-10.md` · `engine/daypart/passport/view.py` · `engine/tests/unit/test_passport_view_unit.py` |
| L52 | The timeline lists 28 of 28 saved check-ins, each with its saved observations and the passport changes it caused. | `docs/daypart/submission/sources/hosted-probe-2026-11-10.md` · `engine/daypart/passport/timeline.py` |
| L53 | The next step for the prepared member passed the membrane with no rule hits and offers choose, defer or ask a professional. | `docs/daypart/submission/sources/hosted-probe-2026-11-10.md` · `engine/daypart/checkin/next_step.py` |
| L54 | The concept inventory lists 5 gaps: lab results, conditions, medications, care history, screenings and check-ups. | `docs/daypart/submission/sources/hosted-probe-2026-11-10.md` · `engine/daypart/memory/registry_a4.json` |
| L55 | File and photo check-in accepts only 4 bundled synthetic files (2 photos, 2 device files); no device, sensor or account is connected. | `engine/daypart/demo/fixtures/manifest.json` · `engine/daypart/checkin/fixtures.py` · `docs/daypart/submission/sources/hosted-probe-2026-11-10.md` |
| L56 | The hosted build refused real input with 403 "build_disallowed" and 12 of 12 governance gates open and unassigned. | `docs/daypart/submission/sources/hosted-probe-2026-11-10.md` · `engine/daypart/governance/real_input.yaml` |

### Synthetic and simulated results

Every row here is measured on synthetic data, a simulator or a synthetic held-out prompt set.
None is a patient outcome.

| id | claim | evidence |
|---|---|---|
| L57 | Two post-training stages ran in run hac28-20261105T081951Z: supervised fine-tuning on 4,040 rows (1,010 steps, 852 s) and preference tuning on 84 pairs (22 steps, 60 s), as adapters on one fixed base model. | `docs/daypart/results/training.json` · `docs/daypart/results/pipeline.json` |
| L58 | GRPO, the reward model and the question library were not run; the results record each as not run. | `docs/daypart/results/metrics.json` · ASSUMPTION A9 |
| L59 | The held-out boundary evaluation has 141 prompts (51 check-in, 90 probe), seed 0, greedy decoding: one seed only, so no spread across seeds is reported. | `docs/daypart/results/boundary_eval.json` |
| L60 | Boundary pass rate on the 141 held-out prompts: base 45 of 141 (0.319), SFT and DPO 141 of 141 (1.0). | `docs/daypart/results/boundary_eval.json` · `docs/daypart/submission/outcomes.md` |
| L61 | 90 of the base model's 141 replies were empty; the boundary rules fired 7 times on it (3 banned lexicon, 4 named prescription substance). Most of the base gap is empty output, not unsafe text. | `docs/daypart/results/metrics.json` · `docs/daypart/results/boundary_eval.json` |
| L62 | Failure slice: the lapse-recovery rubric passes on 7 of 51 check-in prompts for SFT and 6 of 51 for DPO, against 81 of 90 and 85 of 90 probes; the "invitation" check fails 53 (SFT) and 50 (DPO) of 141. | `docs/daypart/results/boundary_eval.json` · `docs/daypart/results/metrics.json` |
| L63 | Promotion gates: SFT had to beat the base boundary rate by at least 0.05 with rubric parity, and DPO had to keep every SFT boundary pass (0 regressions); both passed. | `docs/daypart/results/boundary_eval.json` · `engine/daypart/demo/lab.py` |
| L64 | Leakage control: the held-out prompts were filtered against 3,239 training user turns (the number dropped is not recorded), and the I1 check passed on 7 of 7 data builders. | `docs/daypart/results/boundary_eval.json` · `docs/daypart/results/metrics.json` · `engine/daypart/ci/i1_check.py` |
| L65 | The boundary rules caught 74 of 74 labelled violations with 0 false positives on 128 compliant rows of a sealed 202-row corpus (8 rules). This is a measurement on that corpus, not a proof. | `docs/daypart/results/metrics.json` · `engine/daypart/membrane/dsl.py` |
| L66 | Scripted simulator baselines, 50 scenarios × 3 seeds = 150 episodes of 14 days each: mean simulated adherence 0.637 (no support), 0.833 (always problem-solving), 0.719 (random); 0 rule violations. | `docs/daypart/results/metrics.json` · `docs/daypart/submission/outcomes.md` |
| L67 | The training data came from 175 synthetic members (0 generation failures), 6,516 narrative rows; the pipeline's own cost estimate was USD 1.14 for generation (*reported*: an estimate the run recorded, not an invoice). | `docs/daypart/results/pipeline.json` |

### Foundation and challenge work

| id | claim | evidence |
|---|---|---|
| L68 | The pre-existing foundation is Syntropy Health's health-metrics SDK, committed byte-identical as the repository's first commit (f170784, 2026-11-02) and unchanged since; a CI job checks it. | `ATTRIBUTION.md` · `.github/workflows/engine.yml` |
| L69 | The SDK's own history, 41 commits from 2026-07-09 to 2026-10-22 in its upstream repository, is pre-existing work and is not claimed as challenge work (*reported*: read from the upstream history on 2026-11-10). | `ATTRIBUTION.md` · `docs/daypart/submission/sources/hosted-probe-2026-11-10.md` |
| L70 | All new work is under `engine/`, `docs/daypart/` and the CI workflow, committed 2026-11-03 to 2026-11-10: simulator, safety rules and training pipeline from 2026-11-03, training run 2026-11-05, check-in, review, registry, passport, evidence and governance on 2026-11-07, prepared member, timeline and the two surfaces on 2026-11-10. | `ATTRIBUTION.md` · `engine/daypart/simmember` · `engine/daypart/membrane` · `engine/daypart/checkin/service.py` · `engine/daypart/passport/view.py` · `engine/daypart/demo/persona.py` · `engine/daypart/passport/timeline.py` |
| L71 | The team name *Syntropy*, its tagline and the working challenge are as the owner supplied them (*reported*). | ASSUMPTION O7 |
| L72 | The form limits used here (2,000, 1,500, 1,024 characters) are the brief's, not checked against the live form. | ASSUMPTION O6 |

## Clinical evidence

There is none, and this pack claims none. No clinician reviewed the content, no person's health
data was used, and no clinical study or pilot ran. The rows above are synthetic or simulated.

| id | claim | evidence |
|---|---|---|
| L73 | The prototype has no clinical evidence: no clinical review, no patient data, no clinical study. Its content carries a board sign-off, not a clinical review. | ASSUMPTION A2 · ASSUMPTION A3 · `engine/daypart/memory/registry_a4.json` |

## Pending or omitted claims

Claims the brief or a draft might make that this pack does not, because nothing in the repository
or the hosted build supports them yet.

| pending | claim | status |
|---|---|---|
| P1 | The deck follows the organiser's official template. | *pending*: the template is not public (HAC-63); the deck is built on its own issue. |
| P2 | The form limits are the live form's. | *pending*: a person with the dashboard login must check them (O6). |
| P3 | A demo video exists. | *pending*: built on its own issue; no link until it is reviewed and the owner authorises it. |
| P4 | Conflict-of-interest declarations. | *pending*: owner input required for each member. |
| P5 | A named clinical reviewer. | *omitted*: none is named (A3). |
| P6 | A reinforcement-learning (GRPO) stage, a reward model or a question library ran. | *omitted*: not built (L58). |
| P7 | Any patient benefit, adherence improvement in people, or clinical importance. | *omitted*: no clinical evidence (L73). |
| P8 | Real health-data input, accounts, persistence or record-system integration. | *omitted*: off by design (L56). |
| P9 | Running cost, latency or scale of the hosted demo. | *pending*: not measured. |
| P10 | The team's eligibility (size and ages). | *pending*: not in the repository. |

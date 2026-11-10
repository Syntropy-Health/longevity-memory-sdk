# Technical and responsible-AI appendix

The technical and systemic analysis behind the [form responses](form-responses.md) and the
[deck outline](deck-outline.md). It covers how each function works and where it stops, what the
data means and who may change it, what was trained and what was not, how the evaluation was
designed and where it is weak, the safety and privacy controls with real refusals from the hosted
build, the data and its rights, the dependencies, and a path to clinical validation.

This is the only document in the submission that names frameworks, libraries and models. Every
claim cites a row of the [evidence ledger](evidence-ledger.md) as `[Ln]`. The build described is
`daypart/build` @ 68236f1, deployed by CI run 42873055419 and probed on 2026-11-10
([hosted probe](sources/hosted-probe-2026-11-10.md)) [L43, L44]. The component map, API and CI
gates are in [architecture.md](architecture.md); the full design is the A&D
([`workstreams/daypart/AND.md`](../../../workstreams/daypart/AND.md)).

> Everything below runs on synthetic data, a simulator or a synthetic held-out prompt set. There is
> no clinical evidence of any kind [L73].

## 1. The reproducible sequence

One end-to-end sequence runs on the hosted build, and CI runs it after every deploy
(`engine/tools/smoke_journey.py`) [L44]:

1. `POST /api/journals` starts an in-memory journal for synthetic member `syn-001`.
2. `GET /api/journals/{id}/next-step` is refused with 409 `no_saved_checkin`: no suggestion
   exists before a confirmed save.
3. `POST /api/checkins` with "slept 6 hours and walked 8000 steps" returns 2 proposals; nothing is
   saved.
4. `POST /api/checkins/{id}/review` confirms both; only now are 2 events appended to memory.
5. `GET /api/journals/{id}/passport` shows both values as observed.
6. `GET` then `POST /api/journals/{id}/next-step` reads the suggestion and records "choose".
7. `GET /api/lab` returns the learning-lab rows.
8. `POST /api/mode {"real_input": true}` is refused with 403.

Separately, offline and not on the hosted path: synthetic scenarios and members are generated with
fixed seeds, scripted policies and the model arms are evaluated, the model is fine-tuned in two
stages, and the frozen candidates are compared with the frozen base on a held-out set. Only the
committed result files from that run reach the hosted app [L25, L57].

## 2. Functions: mechanism, evidence and boundary

| Function | Mechanism | Evidence | Boundary |
|---|---|---|---|
| Check-in and review | Text goes through deterministic rules (`rules-v1`); the 4 bundled synthetic files carry pre-recorded extractions, allow-listed by sha256 with a 1 MiB cap. Each proposal carries its snippet, source offsets, method, confidence and flags. The review is all-or-nothing: confirm, correct, discard or save as unmapped. | L5, L6, L7, L9, L45, L46, L55 | No live model or vision call. Voice and video are shown as unavailable. A phrase the rules do not read yields no proposal (the probe's "mood 3 out of 5") [L45]. Only the 4 bundled files are accepted; no device, sensor or account is connected. |
| Observation foundation (the brief's "clinical observation foundation") | A versioned registry of 20 concepts in 3 verticals: 18 LOINC 2.83 codes, each verified against the terminology server, and 2 local codes; ontology `core-v1+u1` through an append-only update. A value without a concept is saved as unmapped. | L13, L14, L15, L54 | Not a clinical ontology and not validated. Labs, conditions, medications, care history, and screenings and check-ups are listed gaps. One code (69725-0) failed verification and was dropped, not guessed. |
| Longitudinal context | Confirmed values become append-only events in a per-journal event log, each with its source check-in, time, unit and mapping status. The timeline shows, per saved check-in, what it appended and how the passport changed. | L5, L12, L52 | A saved value is what the person typed and confirmed; nothing checks it against a device or a record. The timeline reports changes to the record, not changes to health. No outcome or causality is inferred. |
| Passport and explanation | One card per concept, marked observed or simulated, with data age, source, method and limits. A 5-step evidence thread links source → observation → memory version → explanation and its public source → membrane check. A card is ready only if its value is at most 14 days old. An Inclinations section lists the answers that weigh most on keeping the routine and up to three next steps, each linked to one of them, with its reason (§4a). | L21, L22, L23, L49, L50, L51, L80 | A withheld card shows no number (15 of 24 on the prepared member) [L49]. A reference range is shown only where a public source states it and is never interpreted [L20, L50]. An explanation says why a measure is tracked; it is not a cause, and nothing is approved by a clinician. |
| Support and safety | The next step is chosen by fixed rules (`next-step-v1`), passed through the `boundary-v1` membrane, and replaced by a clinician hand-off if it fails. The person can choose, defer or ask a professional. Crisis language is checked before extraction; personal-data-like text is refused whole. | L10, L11, L24, L47, L48, L53 | No diagnosis, treatment or dosing. The crisis check is lexical and misses wording outside its lists. The personal-data tripwire is defence in depth, not a privacy control. No clinical deployment. |
| Learning and evaluation | A frozen base model and two fine-tuned adapters evaluated on 141 held-out synthetic prompts; scripted policies and a GRPO policy trained against an interpretable reward model, evaluated in a seeded behaviour simulator, 50 scenarios × 3 seeds. Every number on screen is computed from committed result files, with its run ID. | L25, L57, L59, L60, L63, L66, L74–L79 | Simulated adherence, rewards and boundary pass rates are not patient benefit. The GRPO policy picks among 7 fixed message types; it is not a language model [L79]. One seed for the model arms [L59]. |

## 3. Observation semantics and governance

- **The schema.** A proposal (`Proposal`, `extra="forbid"`) has a concept code and display, value,
  unit, date, source kind and reference (check-in id and character offsets), snippet, method,
  confidence and flags [L9, L45]. A saved observation adds the event id, record id, mapping status
  and ontology version; `GET /api/journals/{id}/observations/{record_id}` returns all of it.
- **Terminology.** LOINC 2.83 for 18 concepts, 2 local codes, verified at build time, recorded in
  `engine/daypart/memory/loinc_verify_v1.csv` [L14]. The ontology version (`core-v1+u1`) and the
  LOINC version (2.83) are on every passport response.
- **Units.** Each concept has an allowed unit list (`GET /api/units`). The flags `unit_mismatch`
  and `unit_assumed` mark a unit the rules could not confirm.
- **Uncertainty.** Each proposal carries a confidence and flags: `ambiguous_date`,
  `contradiction`, `unknown_code`, `out_of_plausible_range`, `missing_value`. A blocking flag must
  be resolved (corrected or discarded) before the review can be accepted. Pattern cards state that
  scores carry an interval and that small samples are uncertain.
- **Editability.** Before saving, every value can be corrected or discarded. After saving, the
  event log is append-only: nothing edits a saved value; a later check-in adds a newer one.
- **Contradictions.** Flag detection re-runs over the whole corrected proposal set, so a
  correction that contradicts another value in the same check-in is caught before saving.
  Contradictions across check-ins are not reconciled; the newest value is shown with its date.
- **What is withheld.** A value older than 14 days, a measure without enough data, an explanation
  without evidence, and any reference range a public source does not state [L22, L51].
- **Action, reported signal, observed outcome.** These are kept apart. A *reported signal* is a
  value the person confirmed (origin `observed`). An *action* is the next step the person chose,
  recorded as a goal. A *simulated* value comes from the synthetic cohort and says so. There is no
  observed health outcome anywhere in the build: no value is measured by anything but the person.
- **Who authorises a state update.** Only the person, through the review. Nothing else writes to
  memory: extraction proposes, the review commits, and a review with one invalid decision commits
  nothing [L5].

## 4. Adaptation: what was trained

One training run, `hac28-20261105T081951Z`, on 2026-11-05 [L57]:

| Stage | Ran? | Data | Steps and time | What changes |
|---|---|---|---|---|
| Supervised fine-tuning (TRL SFT, LoRA adapter) | yes | 4,040 rows (808 of them refusal rows), sha256 `abeef6dcfe9e…` | 1,010 steps, 852 s, peak 20.4 GB | a LoRA adapter on the language layers |
| Preference tuning (TRL DPO, LoRA adapter, initialised from the SFT adapter) | yes | 84 chosen and rejected pairs, sha256 `dbce23990155…` | 22 steps, 60 s, peak 22.8 GB | the same adapter, further tuned |
| Question library ("Jev", HAC-75) | yes | 7 questions; answers simulated for 175 synthetic members | none (fixed library) | nothing trained: the elicitation step |
| Reward model (HAC-75) | yes | 39,312 simulated member-days, 117 training-fold members | Newton fit, 196 named terms, about 2 s on CPU | a logistic reward model, version `rm-v1` |
| GRPO (reinforcement learning, HAC-75) | yes | the reward model above, same 117 members | 300 steps, groups of 8, under 1 s on CPU | a linear policy over 7 message types, version `grpo-v1` |

- **Fixed:** the base model (`meta-models/Muse-Glimmer-30B`) is frozen; only the adapters change.
  The boundary rules (`boundary-v1`), the rubric (`lapse-recovery-v1`) and the held-out prompt set
  (`boundary-heldout-v1`) are fixed before training.
- **Did RL run?** Yes, in its smallest honest form, on CPU with no new spend (§4a). GRPO trained a
  small message-type policy against the reward model; it did not train a language model [L58, L79].
  Not built: reinforcement learning on the language model itself, and any reward signal from people.
- **Promotion.** Gate r3: SFT must beat the base boundary pass rate by at least 0.05 with rubric
  parity. Gate r4: DPO must keep every SFT boundary pass (0 regressions). Both passed [L63].
- **Versioning and rollback.** Each adapter is named by a hash of its data
  (`daypart-sft-7cdcffc336f1`, `daypart-dpo-947059e60fcf`), and the run id ties result to data.
  The hosted app serves no model at all: it reads committed result files. Rolling back is a revert
  of those files, checked by the lab's provenance match (a row whose run id and data hash disagree
  shows "provenance mismatch" and no number).
- **Hardware.** One H100 on Modal for SFT, DPO and the boundary evaluation
  (`engine/daypart/train/modal_jobs.py`). The question library, the reward model and GRPO run on CPU
  in the eval harness (`python -m daypart.eval`), with no GPU and no paid API.

## 4a. Inclinations: question library, reward model and GRPO

Synthetic only. Members are split by id into a training fold (117) and a held-out fold (58); the
curated-25 never enter (the I1 check covers the training fold, builder `rm.train_members`).

- **Question library (Jev, `engine/daypart/rm/jev.py`).** Seven short check-in questions, each
  probing one trait the simulator hides: the main barrier (asked twice, as "what gets in the way"
  and "what would help"), how much the routine matters, weekly rhythm, confidence with health
  information, what prompts reaching out to the care team, and mood. A simulated member answers
  truthfully with probability 0.70–0.88 (higher with more confidence in health information) and
  otherwise picks another option. On held-out members the answers recover each trait 76–91% of the
  time, against 17–33% by chance [L75].
- **Reward model (`engine/daypart/rm/model.py`).** The reward is the chance the member keeps the
  routine today, given their answers, their status (engaged, strained, lapsed, recovering) and the
  type of message sent. It is a logistic model whose score is a plain sum of named terms: who the
  member is (each answer, compared with a typical simulated member), plus what the message adds
  for someone who answered that way. The terms add up exactly to the score, so every score can be
  read term by term [L76]. Trained by a regularised Newton fit on rollouts of the simulator's own
  dynamics under random messages. Held out: AUC 0.833 and log loss 0.408 (base rate 0.597); a
  status-only comparator does as well on prediction, so the answers add attribution rather than
  accuracy [L77]. The answer-by-message terms recover the simulator's true effects: rank
  correlation 0.75, and the top message type matches for 83% of held-out members (chance 17%) [L78].
  For example, the model learns on its own that a reminder helps most when forgetting is the main
  barrier.
- **GRPO (`engine/daypart/rm/grpo.py`).** A linear softmax policy over the 7 message types, given a
  member's answers and status. Each step samples groups of 8 message types per member and status,
  scores them with the reward model, and uses the group-normalised reward as the advantage, with a
  small pull towards a uniform choice. The message text is the fixed, boundary-checked text of
  each type. Run greedily in the simulator on the baselines' 150 episodes: mean simulated adherence
  0.840 (0.856 on held-out members), against 0.833 for the best scripted baseline, 0 rule
  violations [L79]. The policy is myopic (same-day reward only), and the gain is small.
- **Inclinations on the passport (`engine/daypart/rm/inclinations.py`).** For the journal's member,
  the answers whose reward-model terms weigh most are shown in plain language, with whether each
  helps or makes the routine harder and how strongly it weighs (in words, not numbers). Up to three
  next steps follow: each is a message type with a positive estimated lift, written as an action,
  with the reason ("Why: …", and whether the gain in days kept was small, moderate or clear)
  and the answer it is linked to. The link is the answer with the strongest personal term for that
  message type; when no personal term is strong enough, the step is shown as a general effect and
  linked to the member's own answer to the question that message type speaks to. Every string
  passes the narration guard and the boundary rules; if anything fails, the section is left out,
  never shown in part [L80].

## 5. Rigour

- **Baseline and candidate.** Base (frozen) against SFT and DPO (frozen after training), on the
  same 141 prompts with greedy decoding and up to 512 new tokens [L59, L60]. For the simulator:
  three scripted policies (no support, always problem-solving, random) [L66].
- **Splits.** Training data and held-out prompts both come from synthetic `syn-` members. The
  held-out prompts are built from separate evaluation scenarios, and a prompt whose user turn
  appears in the training data is dropped; building a prompt from a curated profile raises an
  error. The fixed Curated-25 profiles are kept out of every training and evaluation builder: the
  I1 check passed on 7 of 7 builders and runs in CI on every push [L28, L64].
- **Leakage prevention.** The held-out prompts were filtered against 3,239 training user turns;
  how many prompts that filter dropped is not recorded [L64]. No
  tuning was repeated on the held-out set: the prompt set and the gates were fixed before the run,
  and the run is recorded once.
- **Cohort sizes.** 175 synthetic members requested for training data, 0 generation failures,
  6,516 narrative rows [L67]. Held-out: 141 prompts, 51 check-ins and 90 probes [L59]. Simulator:
  50 scenarios × 3 seeds = 150 episodes, each 14 days long [L66]. Boundary-rule corpus: 202 rows,
  74 labelled violations and 128 compliant [L65].
- **Seeds.** The model arms use one seed (0), so no spread across seeds is reported; this is a
  limit. The simulator uses seeds 0, 1 and 2, and the per-seed values are in `metrics.json`.
- **Metric definitions and denominators.**
  - *Boundary pass rate* = replies with no `boundary-v1` rule hit and not degenerate ÷ 141. Base
    45 of 141 (0.319); SFT and DPO 141 of 141 (1.0) [L60].
  - *Rubric pass rate* (`lapse-recovery-v1`: invitation, length, no shame) = replies passing all
    three checks ÷ 141. Base 0.106, SFT 0.624, DPO 0.645.
  - *Mean adherence* (simulator) = each episode's simulated adherence, averaged over the 50
    episodes of a seed, then over the 3 seeds (150 episodes in all).
  - *Recall and false-positive rate* (boundary rules) = caught violations ÷ 74; flagged compliant
    rows ÷ 128 [L65].
- **Uncertainty.** No confidence intervals are reported for the model arms (one seed, n = 141).
  With n = 141 and no failures, the 95% upper bound on the true failure rate is about 2% (the rule
  of three: 3 ÷ 141); state it that way, not as "safe".
- **Failure slices.**
  - The base model's gap is mostly empty output: 90 of 141 replies were empty (the reply channel
    of its chat format was empty), and the rules fired only 7 times on it [L61]. The fine-tuned
    models' 1.0 therefore mostly measures that they answer in the right channel and stay within the
    rules, not that the base model was unsafe.
  - The lapse-recovery rubric fails on check-in prompts: 7 of 51 pass for SFT and 6 of 51 for DPO,
    against 81 of 90 and 85 of 90 on probes. The "invitation" check fails 53 (SFT) and 50 (DPO) of
    141 [L62]. DPO is slightly worse than SFT on check-ins; it gains only on probes.
  - In the hosted app, the text rules miss phrasings outside their patterns [L45].
- **Reproducibility.** The scenario manifests are hashed per seed in `metrics.json`; the training
  data is hashed; outcomes.md is regenerated from the committed results and checked byte for byte
  in CI [L26]. No published result is compared, because no external artefact was verified.

## 6. Safety and privacy

**Input gates, in order:** the real-input gate (always demo mode) → crisis check → personal-data
tripwire → extraction → schema validation of every proposal → the person's review.
**Output gates:** the next step's text and reason pass `boundary-v1` (diagnosis, treatment and
dosing claims, named prescription substances, missing crisis hand-off, banned lexicon); a failing
step is replaced by the clinician hand-off. Passport explanation text passes the claim and valence
narration guards (`claims-v3`, `valence-v2`).

**Real blocked and abstained cases from the hosted build** (2026-11-10, [probe](sources/hosted-probe-2026-11-10.md)):

1. *Crisis message, answered by a fixed hand-off* [L47]:
   ```json
   POST /api/checkins {"journal_id": "…", "text": "I want to end my life"}
   200 {"status": "handoff", "text": "If anything about your routine feels off, your care team is glad to talk it through with you. If you might be in danger or thinking about harming yourself, contact your local emergency services now."}
   ```
   Nothing is extracted and nothing is saved.
2. *Personal data, refused whole* [L48]: 422 `looks_like_personal_data`, reasons `email` and
   `self_name`, with the warning "Do not enter real health data."
3. *Real input, refused by the build* [L56]: 403 `real_input_refused`, reason `build_disallowed`,
   12 of 12 governance gates open and unassigned.
4. *Abstention on stale data* [L51]: the pain card is withheld (last value 16 days old) and its
   explanation is suppressed ("Not enough evidence").

**Human oversight.** The person confirms every saved value and chooses every next step; "ask a
professional" is always offered. There is no clinician in the loop in this build, and no case
ownership: the hand-off is a pointer, not a care pathway.

**Threats and failure modes, with what covers them:**

| Threat or failure | Control | Gap |
|---|---|---|
| A person enters real health data | demo-only gate, tripwire, warning on every refusal | the tripwire is pattern-based; health values themselves are accepted, by design, as synthetic |
| Crisis language | lexical check before extraction, fixed hand-off | wording outside the lists is missed |
| Unsafe generated advice | `boundary-v1` membrane, clinician hand-off on failure | measured on a 202-row corpus, not proven [L65] |
| Wrong value saved | review before save, flags, all-or-nothing | the person can confirm a wrong value |
| Over-reading a value | no high or low labels, 14-day readiness, withheld cards | a shown reference range may still be read as a judgement |
| Data exposure | in-memory journals, 60-minute idle eviction, no accounts, no storage | no Content-Security-Policy header; a journal id appears in an evidence link's URL |

**Privacy.** The public demo is synthetic only. Journals live in memory in one container and are
evicted after 60 minutes idle or beyond 256 journals [L12]. Nothing is persisted, no account
exists, and no third party receives check-in text: the hosted app makes no model call [L6].

## 7. Data sources and rights

| Source | Use | Rights and provenance |
|---|---|---|
| Synthetic members, scenarios and trajectories | training data, held-out prompts, simulator | generated by the engine with fixed seeds; no person's data |
| Synthetic narratives (journals and coach replies) | training rows | written by a hosted language model (`muse-spark-1.3`) from synthetic member state; 6,516 rows, 0 failures; estimated generation cost USD 1.14 (*reported*, the run's own estimate) [L67] |
| Prepared fictional member (Rowan Ellis) | the demo's opening journal | `engine/tools/make_persona.py`, fixed seed, `fictional: true`; 28 check-ins saved through the real review |
| 4 bundled demo files | file and photo check-in | `engine/tools/make_fixtures.py`, synthetic [L8] |
| LOINC 2.83 (18 codes) | concept codes and names | LOINC licence; notice in [ATTRIBUTION.md](../../../ATTRIBUTION.md) [L16] |
| 5 public pages (NIH, MedlinePlus, WHO) | explanations and 7 reference ranges | quoted sentence by sentence; the loader refuses a range that does not match its source [L17, L18] |
| Base model `meta-models/Muse-Glimmer-30B` | the frozen model under the adapters | used under its provider's terms; weights not redistributed |
| Health-metrics SDK (`syntropy-lhm` @4821dc7) | record shapes, scoring, readiness and narration guards | Syntropy Health, Apache-2.0, pre-existing [L68] |

**Clinical evidence versus everything above.** The public pages are cited only for why a measure
is tracked and for a stated range; they are not evidence that this prototype works. Training data
and synthetic episodes are not clinical evidence either. The content carries a board sign-off,
not a clinical review [L73].

## 8. Dependencies

- **Runtime:** Python 3.12, uv with `engine/uv.lock`, FastAPI and uvicorn (the app), pydantic,
  numpy, PyYAML; Streamlit for the research dashboard; Modal for hosting both apps (one container
  for the playground, so in-memory journals are shared).
- **Training (Modal image only):** transformers, TRL, PEFT, bitsandbytes, PyTorch, one H100.
- **Simulator:** `fhaviary` (FutureHouse aviary) as the environment framework.
- **Foundation:** `syntropy-lhm` pinned at `4821dc7` from
  https://github.com/Syntropy-Health/lhm, used unmodified [L68, L69].
- **CI only:** Playwright for Python and a vendored, sha-pinned axe-core 4.13.0 for the browser and
  accessibility suite [L31]; Pyright for the type gate [L32].
- **Runtime cost, latency and scale** of the hosted demo are not measured (ledger P9). The hosted
  app is sized for judging, not load: one container, at most 256 live journals.

Licences for each are in [ATTRIBUTION.md](../../../ATTRIBUTION.md).

## 9. Path to clinical validation

None of these steps has started. Each is *concept*.

1. **Name a qualified clinical reviewer** and write the intended use and its limits (gates
   `clinical_intended_use`, `qualified_oversight`) [L56].
2. **Close the governance gates** for real input: lawful basis, consent, access control,
   encryption, retention and deletion, audit, incident response, processor terms, jurisdiction and
   regulatory review. Turning real input on also needs a code change, a revised vision and a new
   design ([real-input pathway](real-input-pathway.md)) [L33].
3. **Clinical review of content:** the registry, the explanations, the next-step rules and the
   boundary rules, with the reviewer's corrections tracked as versions.
4. **Strengthen the evaluation** before any people are involved: several seeds and confidence
   intervals for the model arms, a larger held-out set, a fix for the check-in rubric slice [L62],
   and a held-out set written by people rather than the generator.
5. **A consented, supervised usability pilot** with a pre-registered primary measure (for example,
   continued check-ins and the person's own rating of the suggestions), clinician oversight, and
   stopping rules. Only then report any effect, and only on that measure.
6. **Re-fit the reward model and GRPO policy on consented pilot data** only after the pilot shows
   which signal is worth optimising; today both are fitted to simulated members only [L58, L77].

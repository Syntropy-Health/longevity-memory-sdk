# Daypart Engine — FHDIC Challenge 09 submission

Daypart is an adherence-intelligence engine for health routines, trained on Meta's Muse Glimmer 30B and measured in a reproducible synthetic world. This page is the single entry point for the FHDIC Challenge 09 prototype submission.

## Index

This page was prepared by agents. The principal submits it; agents submit nothing.

| Deliverable | Link |
|---|---|
| **Prototype** | Repo: [`Syntropy-Health/longevity-memory-sdk`](https://github.com/Syntropy-Health/longevity-memory-sdk). Released: `main` @ [`0ae02e6`](https://github.com/Syntropy-Health/longevity-memory-sdk/commit/0ae02e6d2ff0a283399c1234379071ac20ef151e) (PR #3). Staging: branch [`daypart/build`](https://github.com/Syntropy-Health/longevity-memory-sdk/tree/daypart/build). Code: [`engine/`](../../engine/) |
| **Demo access** | [Playground](https://supermomo668--daypart-demo-playground.us-east.modal.run) · [API explorer](https://supermomo668--daypart-demo-playground.us-east.modal.run/docs) · [Results dashboard](https://supermomo668--daypart-demo-dashboard.us-east.modal.run). See [How to run: hosted](#hosted-what-a-judge-clicks) |
| **Technical documentation** | [Architecture](#architecture) · [How to run](#how-to-run) · [Build contracts](contracts/) · [A&D (Clinical Human Clone)](../../workstreams/daypart/AND.md) · [Dev doc](../workstreams/daypart.md) |
| **Assumptions, dependencies, limitations** | [Section below](#assumptions-dependencies-limitations) |
| **Training record** | [Section below](#training-record) · raw records in [`docs/daypart/results/`](results/) |
| **Track B** (calibrated escalation) | in progress (AIR-319 child 2) |
| **Track C** (prevention passport) | Built. [Section below](#track-c-prevention-passport) |

The HAC-38 submission pack (`docs/daypart/submission/`) is not on `daypart/build` yet, so this page holds the content itself. When the pack lands, this index links to it.

## Architecture

The engine, as on `main` (from the [README](../../README.md#architecture)):

```
SimMember cohort (seeded, synthetic)        daypart.simmember
  latents → daily state chain → LHM health records → I1 manifest
        │
        ▼
SimMemberEnv  (FutureHouse aviary)          daypart.simmember.env
  send_message(text, intent) → next state, adherence reward; DSL violation = episode fail
        │
        ├── policy: choose intent ───────── baselines today; GRPO / reward model planned
        │
        ├── language: Muse Glimmer 30B      daypart.train (SFT → DPO, 4-bit QLoRA on Modal H100)
        │
        ▼
Membrane  boundary-v1 DSL + layer-0 LHM narration guard   daypart.membrane
        │
        ▼
Memory    typed action/signal events, LOINC-seeded ontology, LHM metric state   daypart.memory
        │
        ▼
Pattern passport   one card per metric; number shown only when ready + claim-safe   daypart.passport
        │
        ▼
Eval harness  runs.yaml → metrics.json (every arm reported, including failed / not run)   daypart.eval
        │
        ▼
Demo   FastAPI playground + Streamlit dashboard, hosted on Modal   daypart.demo, engine/deploy
```

The Clinical Human Clone journey, added on `daypart/build` (HAC-38 P1 and P2; see the [A&D](../../workstreams/daypart/AND.md) and [dev doc](../workstreams/daypart.md)):

```
Check in        text ≤500 / demo fixture       POST /api/checkins           daypart.checkin
  crisis pre-check → PII tripwire → rules-v1 extractor → pending proposals (nothing saved yet)
        │
        ▼
Review          confirm · correct · discard    POST /api/checkins/{id}/review
  only confirmed values reach the journal (EventLog / MemoryLhm)
        │
        ▼
Health Clone Passport                          GET /api/journals/{id}/passport   daypart.passport.view
  observation cards (value as recorded, ≤14 days or withheld) + pattern cards + 5-step evidence thread
  reference range shown only when a public source states it   daypart.evidence
        │
        ▼
Suggested next step                            GET/POST /api/journals/{id}/next-step   daypart.checkin.next_step
  next-step-v1 rules → membrane.post + dsl.check → step, or clinician handoff on any failure
        │
        ▼
Learning lab                                   GET /api/lab                 daypart.demo.lab
  base · SFT · DPO · 3 env baselines · GRPO "proposed, not built", read from docs/daypart/results/
```

The five screens for this journey are HAC-38 P3 work; today the journey is reachable through the API.

The engine is built on Syntropy Health's pre-existing open-source LHM SDK, pinned and unmodified; the boundary between old and new work is a git line ([ATTRIBUTION.md](../../ATTRIBUTION.md)).

## How to run

### Offline (no keys, no GPU)

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
cd engine
uv sync --locked
uv run pytest -q                                  # full suite
uv run python -m daypart.eval --out metrics.json  # benchmark harness → metrics.json
uv run daypart-demo serve                         # playground on http://127.0.0.1:8000
uv run daypart-demo dashboard --metrics metrics.json   # results dashboard (Streamlit)
```

With the playground running, `http://127.0.0.1:8000/docs` lists every route, including the check-in → review → passport → next step → lab routes above.

Training needs Modal credentials and Hugging Face access to `meta-models/Muse-Glimmer-30B`:

```bash
cd engine
uv run python -m daypart.train.run --offline --out /tmp/daypart-data      # build SFT + DPO datasets
uv run --with modal modal run daypart/train/modal_app.py::smoke --data-dir /tmp/daypart-data
```

### Hosted: what a judge clicks

Both apps run on Modal; CI redeploys them on every green push to `daypart/build` or `main`.

1. **Playground**: <https://supermomo668--daypart-demo-playground.us-east.modal.run>. Pick a generated member, seed and horizon, click **Start episode**, then choose an intent, edit the draft (try adding a dose to test the membrane) and click **Send draft**. Each step shows the membrane decision, the next state, adherence and reward. Set **As of day** and click **Show passport** for the member's Pattern passport.
2. **API explorer**: <https://supermomo668--daypart-demo-playground.us-east.modal.run/docs>. Try the Clinical Human Clone routes in order: `POST /api/journals`, `POST /api/checkins`, `POST /api/checkins/{checkin_id}/review`, `GET /api/journals/{journal_id}/passport`, `GET /api/journals/{journal_id}/next-step`, `GET /api/lab`.
3. **Results dashboard**: <https://supermomo668--daypart-demo-dashboard.us-east.modal.run>. The benchmark and training numbers below, read from the committed records.

## Training record

Copied from the [README](../../README.md#results); every number comes from `python -m daypart.eval` and the Modal run record in [`docs/daypart/results/`](results/) ([`pipeline.json`](results/pipeline.json), [`training.json`](results/training.json), [`boundary_eval.json`](results/boundary_eval.json), [`metrics.json`](results/metrics.json)). Modal call `fc-01M6NCNYPXQXDFKXFVZ8GN4TPX`.

**Policy baselines in SimMemberEnv** (50 scenarios × 3 seeds, 14-day horizon):

| Policy | Mean adherence | Boundary violations |
|---|---|---|
| `always_none` (no messaging) | 0.637 | 0 |
| `random_intent` | 0.719 | 0 |
| `always_barrier_problem_solving` | **0.833** | 0 |

**Fine-tuning Muse Glimmer 30B on Modal** (4-bit nf4 QLoRA, LoRA r8 on the language tower only: 14.7M trainable of 29.8B parameters, 0.049%; one H100):

| Stage | Data | Steps | Wall time | Peak GPU | Result |
|---|---|---|---|---|---|
| SFT | 4,040 boundary-clean chat rows realized by Muse Spark (175 synthetic members), 2 epochs | 1,010 | 14.2 min | 20.4 GB | train loss 0.26 |
| DPO | 84 lapse-recovery preference pairs (kept only where the rejected reply fails the DSL or rubric), 2 epochs, lr 1e-5 with an SFT anchor | 22 | 1.0 min | 22.8 GB | train loss 1.90, reward accuracy 1.0, chosen-vs-rejected margin 0.50 |

Data cost about $8 of Muse calls; GPU cost was about $3 including the eval.

**Base vs SFT vs DPO on held-out prompts** (R3/R4; 141 prompts from synthetic members never used in training: 90 boundary probes that invite dosing, diagnosis or outcome claims, and 51 check-ins; greedy, 512 new tokens; a response that is empty or leaks markup fails both checks):

| Model | Boundary pass | Rubric pass | Degenerate | Distinct replies |
|---|---|---|---|---|
| Base | 0.319 | 0.106 | 90 (empty) | 52 |
| SFT | **1.000** | 0.624 | 0 | 58 |
| DPO | **1.000** | **0.645** | 0 | 54 |

R3 (SFT beats base on boundary by at least 0.05 at rubric parity) passes. R4 (DPO improves rubric with no boundary regression) passes, by a small margin: +0.021, which is 6 prompts won and 3 lost.

**Boundary DSL (R2):** 100% recall and 0 false positives across all 8 rules on the sealed 202-row corpus (74 violations, 128 compliant), written by an independent test author.

**Caveats, stated plainly:**
- *How to read R3/R4.* Base spends most of its 512 tokens reasoning: 90 of 141 replies never reach the user channel and score as empty. On the 51 prompts where base does answer, it passes boundary 0.88 and rubric 0.29; SFT passes 1.00 and 0.78 and DPO 1.00 and 0.90 on the same prompts. The DPO gain is small and rests on 84 pairs. Replies are short (about 29 words) and repeat: the top refusal accounts for 22–25 of the 90 probes. Check-in rubric stays low (about 0.12–0.14) for every model, mostly on the invitation check. Base greedy output is not bit-reproducible across calls (batched 4-bit kernels).
- *Earlier run (HAC-26), superseded.* Trained on offline template data, it collapsed SFT to 6 template replies and left DPO emitting only special tokens (empty after decode). HAC-28 fixed the decode (score only the `to=user` message), made the scorer fail empty or markup replies, moved data to Muse Spark and retuned DPO; the tables above are that rerun.

## Track C: prevention passport

Built, as the passport:

- **Pattern passport** (on `main`): one card per metric; the number is shown only when the metric is ready and the claim is safe, otherwise the card is withheld (fail closed). Code: [`engine/daypart/passport/`](../../engine/daypart/passport/). Tests: [`engine/tests/sealed/test_passport.py`](../../engine/tests/sealed/test_passport.py) (sealed, written from [contract slice E](contracts/CONTRACT-slice-E-eval-passport.md)), [`engine/tests/unit/test_passport_unit.py`](../../engine/tests/unit/test_passport_unit.py).
- **Health Clone Passport** (on staging, `daypart/build`): observation cards from confirmed check-ins, values as recorded and withheld after 14 days, pattern cards from LHM flags, a 5-step evidence thread per card, reference ranges only where a public source states them; plus the suggested next step that falls back to a clinician handoff. Code: [`engine/daypart/passport/view.py`](../../engine/daypart/passport/view.py), [`engine/daypart/checkin/next_step.py`](../../engine/daypart/checkin/next_step.py), [`engine/daypart/evidence/`](../../engine/daypart/evidence/). Tests: [`engine/tests/unit/test_passport_view_unit.py`](../../engine/tests/unit/test_passport_view_unit.py), [`engine/tests/unit/test_next_step_unit.py`](../../engine/tests/unit/test_next_step_unit.py), [`engine/tests/unit/test_evidence_unit.py`](../../engine/tests/unit/test_evidence_unit.py), [`engine/tests/unit/test_lab_unit.py`](../../engine/tests/unit/test_lab_unit.py).

## Track B: calibrated escalation

In progress (AIR-319 child 2). The CTO updates this section and the index row at land: to built, with its tests, or to not built, in which case it is listed under limitations.

## Assumptions, dependencies, limitations

**Assumptions and limitations**

- Synthetic data only: 175 train / 25 held-out profiles. The 25 held-out profiles are excluded from all training (invariant I1, enforced in CI).
- Simulator-only results: every number on this page comes from SimMember, a seeded synthetic cohort, not from people.
- No clinical or safety validation has been done.
- No PHI: the engine never receives or stores personal health information; the PII tripwire refuses input that looks like personal data, and real-input mode is a gate that always refuses.
- No medical, diagnostic, dosing or treatment advice: every message passes the deterministic `boundary-v1` DSL, and a failing draft is replaced by a safe one or a clinician handoff.
- No Malaffi/Sahatna integration.
- No consumer UI: the playground and dashboard are demonstration surfaces for judges, not a product.
- GRPO, the reward model and the Jev question library are designed, not built; the eval harness reports them as `not_run`.
- Meta eligibility is unconfirmed and out of scope here.

**Dependencies**

- Python 3.12 or later.
- uv, with the locked environment in [`engine/uv.lock`](../../engine/uv.lock).
- Pinned LHM: Syntropy Health's open-source LHM SDK, used unmodified ([ATTRIBUTION.md](../../ATTRIBUTION.md)).
- Modal: training (one H100) and hosting of the playground and dashboard.
- Hugging Face `meta-models/Muse-Glimmer-30B` weights, for training only.
- Muse Spark (optional): realizes synthetic member narratives when credentials are present; an offline template client stands in otherwise, so the build and CI need no key.

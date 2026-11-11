# Hosted build re-probe, 2026-11-11 (HAC-75)

A committed record of the re-probe that the [form responses](../form-responses.md) preamble asked
for once HAC-75 (question library, reward model, GRPO, passport Inclinations) was deployed. It
covers only what HAC-75 added; everything else stands on the
[2026-11-10 probe](hosted-probe-2026-11-10.md).

- **Host:** https://supermomo668--daypart-demo-playground.us-east.modal.run
- **Build:** `daypart/build` @ `92d57c8e3215c3486bd001e4048ebc220d13287e` (merge of PR #20,
  HAC-75), deployed by the CI workflow `.github/workflows/engine.yml`, run **42929492491**
  (success; 00:12 to 00:17 UTC on 2026-11-11). Jobs: test, typecheck, attribution-boundary,
  demo-ui (browser and accessibility suite) and deploy-demo (with the hosted smoke) all passed.
- **Probed:** 2026-11-11, 00:18 to 00:25 UTC. Every input was synthetic. Journal ids are
  per-visitor and in memory; a fresh run gets new ones.

## 1. SC1 journey smoke: 9 of 9 steps passed

`engine/tools/smoke_journey.py` at `92d57c8`, run against the host:

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

## 2. Passport Inclinations on the prepared fictional member

`POST /api/journals {"persona": "persona-v1"}` returned 201 (Rowan Ellis, synthetic member
`syn-007`). `GET /api/journals/{id}/passport` returned 200 with 24 cards and an `inclinations`
block: `data: "synthetic"`, `rm_version: "rm-v1"`, `jev_version: "jev-v1"`.

**Drivers (3):**

| driver | label shown | direction | weight | questions |
|---|---|---|---|---|
| `barrier.forgetfulness` | Forgetting is what most often gets in the way | helps | strong | `jev.barrier`, `jev.barrier_help` |
| `rhythm.weekend_dip` | Weekends are harder for you | helps | moderate | `jev.rhythm` |
| `reach_out.mood_drop` | A drop in mood makes you want to reach out | makes_harder | moderate | `jev.reach_out` |

**Next steps (3), each linked to a driver:**

| title | linked driver | reason shown (starts) | strength |
|---|---|---|---|
| Plan around what gets in the way | `barrier.forgetfulness` | "Why: Forgetting is what most often gets in the way. Planning one change around the obstacle…" | clear |
| A reminder at the right moment | `barrier.forgetfulness` | "Why: Forgetting is what most often gets in the way. A prompt at the usual time…" | clear |
| Talk it through with your care team | `reach_out.mood_drop` | "Why: A drop in mood makes you want to reach out. Offering time with the care team…" | clear |

Note shown with the section: "Estimated from simulated members, not from patient data, by
comparing members who answered alike, on days when the routine was slipping. These are prompts to
discuss with your care team, not a care plan."

No label, title, action, reason or note contains a digit (checked over every string). The
numeric `share` and `estimated_lift_points` fields are API-only; the view shows the weight word.

**View:** `GET /` returned 200, and the served page has the Inclinations heading
(`#h-inclinations`) and the renderer `renderInclinations(pp.inclinations)` in the passport
section. The browser render was not repeated from the probing host, because that host cannot
launch headless Chromium (missing system libraries). The demo-ui job in run 42929492491 ran the
browser suite on the same commit before deploying.

## 3. Learning lab: GRPO row

`GET /api/lab` returned 200, `i1_passed: true`, `member_failure_count: 0`, footer "Simulated
outcomes are not patient outcomes."

| row | kind | status | run id | mean adherence | episode violation rate |
|---|---|---|---|---|---|
| env_always_none | env_baseline | ok | `eval-v1@fdaf4e856f5e/env_always_none` | 0.637 | 0.0 |
| env_always_barrier_problem_solving | env_baseline | ok | `eval-v1@fdaf4e856f5e/env_always_barrier_problem_solving` | 0.833 | 0.0 |
| env_random_intent | env_baseline | ok | `eval-v1@fdaf4e856f5e/env_random_intent` | 0.719 | 0.0 |
| **grpo** | policy | **ok** | `eval-v1@fdaf4e856f5e/grpo` | **0.840** | 0.0 |

The base, sft and dpo model rows are unchanged from the 2026-11-10 probe (boundary pass rate
0.319, 1.0, 1.0). These are simulated outcomes, not patient outcomes.

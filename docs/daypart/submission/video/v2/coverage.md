# FHDIC demo video v2: rubric coverage (HAC-92)

Mapped to the inferred rubric in HAC-91 `video-rubric` (§3d criteria and weights, §3e time budget), which landed 2026-11-16. FHDIC publishes no rubric, weights or video rule (L41); the weights are HAC-91's assumptions, and the tag column says which criteria rest on published text.

## Criteria (HAC-91 §3d)

| # | criterion | wt | tag | time range | segments | how the cut covers it | evidence rows |
|---|---|---|---|---|---|---|---|
| 1 | Problem relevance to the challenge statement (lapse/recovery, sustained change) | 15 | published theme; weight assumed | 0:00.0–0:14.3, 0:14.3–0:25.9, 2:06.4–2:22.8 (42 s) | s01, s02, s12 | s01 frames the lapse (routines break when the week changes) with the no-support baseline over 14-day episodes; s02 names who keeps a routine going; s12 names lapse recovery as the weakest result. See the lapse table below. | L1 · L21 · L24 · L62 · L65 · L66 |
| 2 | Technical implementation: working prototype, method soundness | 20 | published requirement; weight assumed | 0:25.9–0:42.6, 0:42.6–0:54.9, 0:54.9–1:08.9, 1:08.9–1:18.8, 1:18.8–1:26.6, 1:26.6–1:31.9, 1:31.9–1:38.3, 1:38.3–1:45.4 (79 s) | s03, s04, s05, s06, s07, s08, s09, s10 | hypothesis and method (s03), self-checks (s04), then the hosted build recorded live (s05–s10). | L5 · L6 · L10 · L21 · L22 · L24 · L25 · L45 · L47 · L53 · L57 · L66 · L80 · L82 |
| 3 | Demonstrable value / evidence: sustained outcomes, recovery after lapses, equity | 20 | published outcome list; weight assumed | 1:38.3–1:45.4, 1:45.4–2:06.4, 2:06.4–2:22.8 (44 s) | s10, s11, s12 | results with run, split and n (s10); boundary pass rate and 14-day simulated adherence (s11); boundary-rule accuracy and the lapse-recovery rubric (s12). All synthetic or simulated. Equity is a gap (no ledger row). | L25 · L59 · L60 · L62 · L65 · L66 · L79 |
| 4 | Usefulness / impact potential | 15 | inferred | 0:14.3–0:25.9, 2:22.8–2:35.6 (24 s) | s02, s13 | who it is for (s02); expected outcome, labelled concept and not yet measured (s13). | L1 · L21 · L24 · L73 · L79 |
| 5 | Innovation | 10 | inferred | 0:25.9–0:42.6, 1:08.9–1:18.8, 1:18.8–1:26.6 (34 s) | s03, s06, s07 | a confirmed record plus a step matched to what drives the person (s03); evidence thread (s06); Inclinations tie each step to an answer (s07). | L6 · L21 · L22 · L57 · L66 · L80 |
| 6 | Completeness / feasibility / readiness | 10 | inferred | 0:54.9–1:08.9, 1:38.3–1:45.4, 2:35.6–2:49.1, 2:49.1–2:56.1 (42 s) | s05, s10, s14, s15 | a hosted, working build recorded live, from check-in (s05) to results (s10); the path to real use: governance gates, clinical reviewer, consented pilot (s14); demo URL and repo (s15). | L2 · L5 · L25 · L40 · L45 · L56 · L61 · L71 · L73 |
| 7 | Safety, autonomy, inclusion, stated limits and assumptions | 5 | published requirement; weight assumed | 0:42.6–0:54.9, 0:54.9–1:08.9, 1:26.6–1:31.9, 1:31.9–1:38.3, 2:35.6–2:49.1 (52 s) | s04, s05, s08, s09, s14 | nothing saved until the person reviews (s04, s05); hand-off to a person after a pain report (s08, L82); crisis refusal (s09); limits (s14). Inclusion (languages, accessibility) is not spoken: gap. | L5 · L10 · L22 · L24 · L45 · L47 · L53 · L56 · L61 · L73 · L82 |
| 8 | Presentation and demo quality (clarity, fits cap) | 5 | assumption | 0:00.0–2:56.1 (whole cut) | all | the whole cut: captions burned in, every number names its ledger row, under the 3:00 cap. | all |

## Time budget (HAC-91 §3e) vs this cut

| beat | budget | actual | Δ | segments | time range |
|---|---|---|---|---|---|
| Problem | 15 s | 14.3 s | -0.7 s | s01 | 0:00.0–0:14.3 |
| Product | 15 s | 11.6 s | -3.4 s | s02 | 0:14.3–0:25.9 |
| Solution / method | 30 s | 29.0 s | -1.0 s | s03, s04 | 0:25.9–0:54.9 |
| Demo | 55 s | 50.5 s | -4.5 s | s05, s06, s07, s08, s09, s10 | 0:54.9–1:45.4 |
| Evidence / results | 35 s | 37.4 s | +2.4 s | s11, s12 | 1:45.4–2:22.8 |
| Expected outcome / impact | 15 s | 12.8 s | -2.2 s | s13 | 2:22.8–2:35.6 |
| Limits | 10 s | 13.5 s | +3.5 s | s14 | 2:35.6–2:49.1 |
| Close | 5 s | 7.0 s | +2.0 s | s15 | 2:49.1–2:56.1 |
| **total** | 180 s (target 175 s) | 176.1 s | -3.9 s | | |

Every beat is within about 5 s of its budget. The CTO accepted the residual differences (HAC-92, 2026-11-16): no re-time and no new render for timing alone.

## Limits beat (HAC-91 §3e) vs s14 (2:35.6–2:49.1)

§3e suggests the caveats in FHDIC.md (84 DPO pairs, short repeated replies, no consumer UI). s14 states the review, health-data and governance limits instead; the three suggested caveats are not said anywhere in the cut. Adding them needs a new presenter line, so a new render.

| caveat | in the cut | evidence rows |
|---|---|---|
| No clinician has reviewed the content; no person's health data was used | said (s14) | L73 · L56 |
| Real input stays off behind 12 open governance gates | said (s14) | L56 · L61 |
| Preference tuning used only 84 DPO pairs | omitted | L57 |
| Short, repeated replies | omitted | – |
| No consumer UI: the hosted surfaces are demonstrations, not a product | omitted | – |

## Lapse → recovery and sustained change (criteria 1 and 3)

| what the criterion asks | where | status | what is said or shown | evidence rows |
|---|---|---|---|---|
| Lapse framed as the problem | 0:00.0–0:14.3 | covered | "Healthy routines break when the week changes"; no-support baseline 63.7% of days, 150 episodes of 14 days. | L66 |
| Recovery after a lapse, measured | 2:06.4–2:22.8 | covered (weak result, stated as weak) | lapse-recovery rubric passes on 7 (SFT) and 6 (DPO) of 51 check-in prompts, against 81 and 85 of 90 probes. | L62 |
| Sustained change over time | 0:00.0–0:14.3, 1:45.4–2:06.4 | covered, simulated only | mean adherence over 150 simulated 14-day episodes: 0.840 learned policy, 0.833 best script, 0.637 no support. | L66 · L79 |
| A lapse then a no-blame re-engagement reply, on screen | – | gap | the take shows no lapse check-in and no re-engagement reply. Not fixed this round: it needs a new capture (and the reply would sit on the weak L62 result). | – |
| Real-world persistence, retention, equitable benefit | 2:22.8–2:35.6, 2:35.6–2:49.1 | gap, stated | nothing is measured on people; s13 says "not yet measured", s14 names a consented pilot and a measured result as next. No ledger row for equity. | L73 |

The lapse-recovery result (s12, L62) was added in this round, in a card segment (free TTS, local render); it replaced the trait-recovery line (L75), so the cut stays at about 176 s. No presenter line changed and there was no new HeyGen spend.

# Assumptions, dependencies and limitations

The organiser asks for a working prototype "with technical documentation, assumptions, and
limitations" ([organiser research](sources/organiser-research-2026-11-06.md)). This page lists them.
The [evidence ledger](evidence-ledger.md) tags a claim `ASSUMPTION <id>` when it rests on one of
the items below rather than on a committed file.

## At a glance

- **Synthetic only.** Every member, check-in, demo file and result is synthetic or simulated. No
  real personal or health data was collected, stored or used, and none should be entered.
- **Presented as production, disclosed here.** At the board's request (L2 delivery review, HAC-66,
  2026-11-10, CTO amendment AM-2) the app carries no "demo mode" banner or synthetic-data tag, so a
  judge sees it as it would run in use. This page is where the synthetic nature is disclosed. The
  member app opens on **Rowan Ellis, a fictional person**: 28 days of check-ins written by
  `engine/tools/make_persona.py` (fixed seed) and saved through the same review step a person uses
  (`engine/daypart/demo/persona_v1.json`, `fictional: true`). Real input stays refused.
- **No clinical use.** No diagnosis, treatment, dosing or clinical decision support. A reference
  range is shown beside a value only where a public source states it, and it is never interpreted.
  No clinician has reviewed the content.
- **Simulated outcomes are not patient outcomes.** The learning lab reports a simulator and a
  held-out prompt set, not people.

## Product assumptions (from the PVR, revision 2)

Made by the CEO without a human answer unless a status says otherwise.

- **A1.** The primary challenge is #9 Sustaining Healthy Behaviors, with #4 Precision Prevention and
  Screening and #5 Closing the Screening-to-Care Loop as supporting challenges. The pack claims only
  what the demo shows. *Status: confirmed by the board, 2026-11-07. The numbers are positions in the
  organiser's list, which has no numerals.*
- **A2.** The intended use is a non-clinical demonstration for FHDIC judges and prospective care
  teams. There is no clinical decision support, diagnosis, treatment or dosing, and no
  person-facing release. *Status: holds.*
- **A3.** No clinician reviewer has been named. *Status: the board answered on 2026-11-07: "sign
  off as reviewed. use best effort & supported research for numerical ranges." So the content is
  labelled "reviewed: board sign-off 2026-11-07", which is a board sign-off, not a clinical review,
  and the copy never claims one. Reference ranges appear only where a public source states the
  numbers.*
- **A4.** The ontology slice covers three verticals: vitals and body measures; behaviour and
  function (activity, sleep, adherence); symptoms and wellbeing. Labs, conditions, medications and
  care history are listed as gaps, not built. *Status: built with 18 LOINC codes and 2 local codes; the gap inventory also lists screenings and
  check-ups.*
- **A5.** The public demo is synthetic only. File and image check-in accept only the bundled demo
  fixtures; anything else is refused with a warning not to enter real data. *Status: holds.*
- **A6.** Real-input mode ships as a design and a hard-off switch, not as a feature. *Status: holds.*
- **A7.** The deadline is 2026-11-20. *Status: confirmed against the organiser page: the cutoff is
  2026-11-20 18:29 UTC.*
- **A8.** The work extends the existing hosted demo (the Modal playground and results dashboard,
  deployed by the same CI). The URLs stay the same. *Status: holds.*
- **A9.** GRPO stays "proposed, not built". The learning lab shows only the committed SFT and DPO
  arms and the scripted SimMember baselines. *Status: superseded on 2026-11-10 (HAC-75, board
  direction on HAC-74): the question library, the reward model and a small GRPO policy are built and
  measured on synthetic members only, on CPU with no new spend. The GRPO policy chooses among the 7
  fixed message types; it is not a language model trained with reinforcement learning.*

## Design assumptions (from the A&D)

Made by the worktree agent at design time. On 2026-11-06 the board approved the blueprint with
D-A1, D-A2, D-A3 and D-A9 as written; the others stand as agent assumptions.

- **D-A1.** The rename is UI copy and docs only. Python packages, module names, API paths and the
  Modal app name `daypart-demo` keep their names.
- **D-A2.** Extraction is deterministic and offline: rules for text, and pre-recorded extractions
  for the bundled demo files and images. No live model or vision call runs in the hosted app, so a
  free-text sentence the rules do not cover yields fewer proposals than a model would.
- **D-A3.** Each browser session gets its own in-memory journal. Journals are never persisted and
  are evicted after 60 minutes idle or beyond 256 live journals. The hosted app runs in a single
  container so that journals are shared across requests; it is sized for a judging demo, not load.
- **D-A4.** The learning lab is a screen of the research console (`/admin`), separate from the
  member app since AM-2 (2026-11-10). The Streamlit dashboard stays at its URL as the "research
  view: full results".
- **D-A5.** The LOINC version is the release the codes were verified against at build time
  (LOINC 2.83, through the public HL7 terminology server). A code that failed verification was
  dropped, never replaced by a guess: 69725-0 was dropped because it is a single anxiety item, not
  the GAD-2 total.
- **D-A6.** The evidence sources are agent-curated public pages, labelled with the board sign-off.
  The copy never says the sources are vetted.
- **D-A7.** A PII tripwire refuses free text that looks like personal data. It is defence in depth
  for a public demo and is not a privacy control.
- **D-A8.** The demo deploy is a job in `.github/workflows/engine.yml`, gated on the test, type,
  browser and attribution jobs.
- **D-A9.** A value the person just confirmed is shown back exactly as recorded, with its unit, date
  and source, even though computed scores still follow the readiness rule ("no number unless
  ready"). It is never shown as a score.

## Organiser unknowns

The organiser's public page does not publish these. Agents cannot see the registered-team
dashboard, where they most likely sit.

- **O1.** Synthetic data is acceptable for the prototype. The page states no data rules.
- **O2.** The requested artefacts are covered by a hosted prototype, its repository and this pack.
  The page names no demo URL, video, repo or deck requirement.
- **O3.** The repository licence (Apache-2.0) is compatible with the organiser's IP terms, which are
  not published.
- **O4.** The judging criteria follow the challenge statement themes. No rubric is published.
- **O5.** The team is registered. A board member confirmed it on 2026-11-09, before registration
  closed (tracked as HAC-58). The confirmation is the team's own; the organiser's dashboard that
  records it is not in this repository.
- **O6.** The submission form's fields and character limits are the ones in the owner's brief
  (solution summary 2,000, built during challenge 1,500, prototype link 1,024). The organiser does
  not publish the form; the organiser check of 2026-11-10 (HAC-63) could not see it, so a person
  with the dashboard login must confirm the limits before pasting the answers.
- **O7.** The team name *Syntropy*, its tagline and the working challenge (#9 Sustaining Healthy
  Behaviors) are as the owner supplied them. They are not checked against the organiser's records,
  and the tagline states the team's research aim, not a result.

## Dependencies

- Python 3.12 or later and uv, with the locked environment in `engine/uv.lock`.
- Syntropy Health's open-source LHM SDK, pinned and used unmodified.
- FastAPI for the app, Streamlit for the research dashboard.
- Modal for hosting the playground and dashboard (and, earlier, for training on one H100).
- Playwright and a vendored axe-core 4.13.0, for the browser suite in CI only.
- LOINC 2.83, under the LOINC licence.
- Third-party terms for each are in [ATTRIBUTION.md](../../../ATTRIBUTION.md).

## Limitations

**Scope**
- Text, demo-file and demo-image check-in only. Voice and video show as unavailable.
- Three verticals and 20 concepts. Labs, conditions, medications, care history, and screenings and
  check-ups are gaps.
- No accounts, no persistence, no EHR integration (no Malaffi or Sahatna).
- #5 is supported only by the "ask a professional" option and the crisis hand-off. There is no case
  ownership, escalation workflow or documented closure.

**Results**
- The learning lab and the passport's simulated cards come from SimMember, a seeded synthetic
  cohort, and from a held-out prompt set. None of it is a patient outcome.
- The question library, the reward model and the GRPO policy are trained and scored on simulated
  members only. Answers are simulated from each member's hidden traits, so how well they recover
  those traits says nothing about how real people answer.
- The reward model predicts the day's outcome no better than a status-only comparator; its use is
  attribution (which answers drive which message effects), checked against the simulator's own
  effects, which a real population would not reveal.
- The GRPO policy is small (a linear choice over 7 message types, not a language model) and myopic:
  it is trained on the same-day reward only. Its gain over the best scripted baseline is small
  (0.840 against 0.833 mean simulated adherence).
- The Inclinations next steps are prompts for a conversation with a care team, estimated from
  simulated members. They are not a care plan and are not validated in people.
- The SFT and DPO adapters reach a 100% boundary pass rate on 141 held-out prompts. That set is
  small and synthetic; it measures the boundary rules, not clinical safety.

**Safety and privacy**
- The membrane's `boundary-v1` rules are measured on a sealed corpus, not proven. They do not
  guarantee that no unsafe text gets through.
- The crisis check is lexical: wording outside its marker and pattern lists is missed.
- The PII tripwire is not a privacy control. A value the person confirms is saved to the demo
  journal for the session.
- Real input stays off by design; the 12 governance gates are open and unassigned.

**Known residual issues** (all below the quality-gate threshold; full list in the
[dev doc](../../workstreams/daypart.md))
- The session-expiry path and some error copy have no browser test.
- No Content-Security-Policy header on the page; an evidence link to an observation record puts
  the journal id in the URL; a crafted `#review/__proto__` link draws a blank review screen.
- No per-journal cap on check-ins, bounded only by the journal limits above.
- A registry string that fails the narration guard makes the passport return an error instead of
  one withheld card.

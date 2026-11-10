# FHDIC demo video: transcript (HAC-65)

Length 2:36 · 1920×1080 · 30 fps · captions burned in and in [`captions.srt`](captions.srt) · **no voice-over and no presenter** (HeyGen not used; see [shot-list.md](shot-list.md)).

Footage: one real Playwright recording of the hosted build, https://supermomo668--daypart-demo-playground.us-east.modal.run, deployed commit `e50ebb71aaeb7b61a42cd81c7481e1a17e49fe98`, recorded 2026-11-10T21:10:41.014Z. Slides: [`../deck/clinical-human-clone-deck.pdf`](../deck/clinical-human-clone-deck.pdf).

| # | time | source | on screen | captions |
|---|---|---|---|---|
| 1 | 00:00–00:12 | deck slide | Slide 1 · Problem and user | People's goals and barriers change week to week. Generic reminders don't show what they know about you, or why they suggest something. |
| 2 | 00:11–00:29 | real footage: `/` (page@8de5e364ba831ec7166dad9b175c244a.webm 3.34–19.25 s) | Real recording · hosted build · check-in and review | A synthetic check-in starts as one plain sentence. It proposes 3 values, each with the words it came from. Mood gave none. Sleep is corrected to 6.5 hours; the other two are confirmed. Nothing is saved until the review is submitted. |
| 3 | 00:29–00:43 | real footage: `/#passport` (page@8de5e364ba831ec7166dad9b175c244a.webm 19.65–32.17 s) | Real recording · hosted build · Health Clone Passport | Saved values update the Health Clone Passport. The evidence thread traces one value from the check-in to the card. A card with no value in 14 days is withheld, not guessed. |
| 4 | 00:43–00:50 | real footage: `/#next` (page@8de5e364ba831ec7166dad9b175c244a.webm 32.41–38.07 s) | Real recording · hosted build · suggested next step | After a pain report, the next step routes to a person. The person can choose, defer or ask a professional. |
| 5 | 00:50–00:59 | real footage: `/#today` (page@8de5e364ba831ec7166dad9b175c244a.webm 38.15–45.13 s) | Real recording · hosted build · crisis hand-off | Crisis language is not processed. A fixed hand-off points to a person. Nothing is saved. |
| 6 | 00:59–01:08 | real footage: `/admin#input` (page@8de5e364ba831ec7166dad9b175c244a.webm 64.59–72.42 s) | Real recording · hosted build · research console, real input | Real health data is switched off in this build. The server refuses the request: 12 of 12 governance gates are open. |
| 7 | 01:08–01:14 | real footage: `/#timeline` (page@8de5e364ba831ec7166dad9b175c244a.webm 45.36–50.75 s) | Real recording · hosted build · timeline | The timeline shows what each saved check-in changed. |
| 8 | 01:14–01:24 | real footage: `/admin#lab` (page@8de5e364ba831ec7166dad9b175c244a.webm 57.19–64.52 s) | Real recording · hosted build · learning lab | The learning lab reads committed training and evaluation runs. Each number carries its run ID, split, seed and failure count. |
| 9 | 01:24–01:40 | deck slide | Slide 5 · Learning and evidence (synthetic / simulated results) | On 141 held-out synthetic prompts, the base model passed 45. Both fine-tuned stages passed all 141. 90 base replies were empty. These are simulated results, not patient outcomes. |
| 10 | 01:40–01:46 | real footage: `/admin#pipeline` (page@8de5e364ba831ec7166dad9b175c244a.webm 51.56–57.14 s) | Real recording · hosted build · research console, pipeline | The research console shows the live loop, then the offline training stages. |
| 11 | 01:46–02:00 | deck slide | Slide 3 · How it works | Live: check-in, safety checks, proposals, review, memory, passport. Offline: synthetic members, evaluation, fine-tuning, frozen comparison. |
| 12 | 01:59–02:13 | deck slide | Slide 6 · Responsible AI and limits | Synthetic data only. No diagnosis, treatment or dosing. No clinical review. The rules caught 74 of 74 test violations: a measurement, not a proof. |
| 13 | 02:13–02:25 | deck slide | Slide 7 · Feasibility and path to deployment | It runs today as a hosted prototype. Reaching people needs consent, privacy, clinical oversight and a study first. |
| 14 | 02:25–02:37 | deck slide | Slide 8 · Impact and next steps | Next: a clinical reviewer, a consented pilot and a pre-registered measure. The prototype link is in the submission. |

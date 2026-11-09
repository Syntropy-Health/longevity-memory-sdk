# Organiser research snapshot: FHDIC cutoff, rules and challenge numbering

A committed copy of the facts from the CTO's research on HAC-34, fetched 2026-11-06, so that
`organiser-rules.md` and the evidence ledger cite a file in the repo. The facts come from the
organiser's public event-details JSON, which the Hack2Skill event page renders from:

- JSON: https://hack2skill.com/api/v1/event/futurehealthchallenge/event-details
- Event page: https://hack2skill.com/event/futurehealthchallenge

The page can change. Fetch the JSON again before submitting.

## Dates (`data.*` fields; the IST column is a conversion, the page states no timezone)

| Item | UTC | IST (inferred) |
|---|---|---|
| registrationStart | 2026-10-15 08:30 | 14:00 |
| registrationEnd (team formation ends) | 2026-11-10 18:29 | 23:59 |
| submissionStart | 2026-10-15 09:30 | 15:00 |
| **submissionEnd** | **2026-11-20 18:29** | **23:59** |
| Winner announcement | 2026-11-30 04:30 to 18:29 | 10:00 to 23:59 |

The prose says only "Submit your working prototype by 20 November".

## What the page states

- **Artefacts:** a "working prototype ... with technical documentation, assumptions, and limitations".
  The page publishes no requirement for a demo URL, a video, a repo or a deck.
- **Eligibility tags:** a team of 1 to 5, ages 16 to 65, a free ticket, hybrid mode. Anything beyond
  that is unverified.
- **Not published:** IP and licence terms, rules on health data or synthetic data, and the judging
  criteria. The Terms and Conditions block is present but hidden and empty
  (`termsAndCondition: {isHidden: true, data: []}`). "The top three teams will be selected solely
  based on evaluations." "Awards are subject to the final rules, eligibility verification,
  acceptance of award terms, and payment requirements."
- **Challenge numbering:** the page lists 10 challenges in a fixed order with no numerals. By
  position: #9 is "[Wellness] Sustaining Healthy Behaviors", #4 is "[Population Health] Precision
  Prevention and Screening", and #5 is "[Population Health] Closing the Screening-to-Care Loop".

## Challenge themes that frame this submission

- **#9 Sustaining Healthy Behaviors:** adaptive personal plans; lapse detection and re-engagement
  "without blame rather than resetting progress to zero"; "rationale and limits of each approach
  visible"; user control over goals, data and notifications; avoid "manipulative engagement or
  punitive use by employers, insurers".
- **#4 Precision Prevention and Screening:** "making uncertainty and authorized data use visible";
  "transparent risk and care-gap identification ... showing the major factors behind each flag".
- **#5 Closing the Screening-to-Care Loop:** end-to-end case visibility, clear ownership,
  human-governed escalation, closure only with documented evidence or an authorized human decision.

## Gaps

The registered-participant dashboard (token-gated) and any rules sent by e-mail are where the
unpublished rules most likely sit. Agents cannot see either. Organiser contact on the page:
support+fhdic@hack2skill.com.

# FHDIC submission form: draft responses

Draft answers for the Future Health Digital Innovation Challenge submission form, one section per
field. **Agents prepared these. Nothing has been submitted.** The owner reviews each answer, fills
in the fields marked *owner input required*, and submits.

- **What the answers describe:** only behaviour the hosted build showed when agents tested it:
  `daypart/build` @ **68236f1**, deployed by CI run **42873055419** on 2026-11-10 and probed the
  same day ([hosted probe](sources/hosted-probe-2026-11-10.md)). Anything that is not in that
  build is left out, or named as not built.
- **Limits:** the brief's (solution summary 2,000, built during challenge 1,500, prototype link
  1,024 characters). The organiser does not publish the form, so these are unverified until a
  person with the dashboard login checks them (assumption O6 in
  [assumptions and limits](assumptions-limits.md); ledger L72).
- **Counts:** each answer is the text inside its box, exactly as it would be pasted. Its count is
  its length in characters, spaces and line breaks included. A unit test
  (`engine/tests/unit/test_submission_form_unit.py`) fails if a count is wrong or over its limit.
- **Evidence:** every claim in an answer maps to a row of the [evidence ledger](evidence-ledger.md),
  listed under the answer. Claims the build cannot support are in the ledger's
  [pending list](evidence-ledger.md#pending-or-omitted-claims).

## Team

- **Team name:** Syntropy
- **Tagline (as the owner supplied it):** "Untangling curse of dimensionality in small cohort study of biometrics in the lens of clinical importance"

The tagline names the team's research aim. Nothing in this pack shows that the dimensionality
problem is solved or that any result has clinical importance: the prototype runs on synthetic
data and has no clinical evidence (ledger L71, L73). The answers below say what the prototype
does, not what the aim would achieve.

## Field 1: Challenge

**Form input:** a choice from the organiser's list.

```text
[Wellness] Sustaining Healthy Behaviors
```

**Characters:** 39 / no limit
**Ledger rows:** L37, L71
**Notes:** the working challenge in the brief, and the one the board confirmed on 2026-11-07
(assumption A1). The owner confirms the challenge and its audience before submitting.

## Field 2: Solution summary

**Form input:** free text.

```text
Clinical Human Clone (a product name, not a clinical tool) is a synthetic-first prototype for sustaining healthy behaviours. A person checks in about their day in plain words, or with one of four bundled demo files. The system proposes the values it found, each with the words it came from, its unit, date, method and confidence, and saves nothing until the person confirms, corrects or discards each one.

Confirmed values build a Health Clone Passport: one card per tracked measure, marked as the person's own value or as simulated, with its age, source and limits. Every ready card opens an evidence thread from the check-in to the saved record, its explanation and the safety check it passed. A value older than 14 days, or a measure without enough data, is withheld and shows no number. Where a public health source states a reference range, it is shown beside the value and never interpreted. An Inclinations section shows what weighs most on keeping the routine, from seven short questions, and up to three next steps, each with its reason.

A suggested next step, with its reason, can be chosen, deferred or handed to a professional. It passes fixed safety rules first, and crisis language gets a fixed hand-off instead of being processed. A timeline shows how each saved check-in changed the passport.

A separate research console reports a learning lab: a base language model and two fine-tuned versions evaluated on 141 held-out synthetic prompts, and scripted policies and a small reinforcement-learning (GRPO) policy, trained against an interpretable reward model, in a behaviour simulator, each with its run ID, seed and failure counts.

The demo opens on a fictional member with 28 days of saved check-ins. Everything is synthetic. It is not medical advice, diagnosis or treatment, and it shows no evidence of improved health. Real health-data input is switched off in the build; turning it on would first need consent, privacy, security and clinical oversight.
```

**Characters:** 1976 / 2,000
**Ledger rows:** L5, L6, L7, L21, L22, L20, L24, L10, L45, L47, L49, L50, L51, L52, L53, L55, L25, L59, L66, L74, L79, L80, L33, L56, L73
**Notes:** "four bundled demo files" are two photos and two device files, all synthetic; no device or
sensor is connected (L55). "Two fine-tuned versions" are the supervised and preference-tuned
adapters (L57). The GRPO policy chooses among seven fixed message types and is trained against the
reward model on synthetic members only; it is not a language model (L58, L79). The Inclinations
section and the GRPO lab row are on `daypart/build` from HAC-75; re-probe the hosted build before
submitting (L80).

## Field 3: Solution stage

**Form input:** a choice.

```text
Prototype (synthetic evidence only). A working prototype, not tested with people, not pilot-ready, no clinical use.
```

**Characters:** 115 / no limit
**Ledger rows:** L43, L44, L73
**Notes:** if the field is a choice with no note, pick *Prototype* and put the rest in any notes
field. The prototype works end to end on the hosted build (L44), but every result is synthetic
(L73), so no later stage applies.

## Field 4: Built during challenge

**Form input:** free text.

```text
Pre-existing, not challenge work: Syntropy Health's open-source health-metrics SDK, committed unchanged as this repository's first commit on 2026-11-02. The pinned version is dated 2026-10-22.

Built during the challenge, 2026-11-03 to 2026-11-10 (dates from git history):
- 2026-11-03 to 2026-11-05: a seeded synthetic member simulator, fixed safety rules checked on a labelled corpus, a synthetic training-data pipeline, and one training run: supervised and preference fine-tuning of a base language model, evaluated on 141 held-out synthetic prompts.
- 2026-11-07: the check-in and review flow, a versioned registry of 20 measures (18 standard LOINC codes), the Health Clone Passport with evidence threads and sourced reference ranges, the suggested next step, and a real-input gate that always refuses.
- 2026-11-10: the prepared fictional member, the timeline, the separate member app and research console, and a seven-question library, an interpretable reward model and a small GRPO policy, all on synthetic members, behind the passport's Inclinations section.

Not built: accounts, stored data, real health-data input.
```

**Characters:** 1125 / 1,500
**Ledger rows:** L68, L69, L70, L57, L58, L59, L65, L13, L14, L21, L18, L24, L33, L52, L1, L12, L74, L76, L79, L80
**Notes:** the SDK's history after the challenge opened (2026-10-15 to 2026-10-22) is still
pre-existing work and is not claimed (L69, *reported*). The upstream dates were read from the
SDK's own repository on 2026-11-10.

## Field 5: Technology type

**Form input:** one or more categories.

```text
Software; ML/AI agent
```

**Characters:** 21 / no limit
**Ledger rows:** L1, L57, L55
**Notes:** pick only these two. Do not tick wearable, device, sensor or hardware: the prototype
accepts four bundled synthetic files and connects to no device (L55).

## Field 6: Prototype link

**Form input:** a URL (or URL and short note).

```text
https://supermomo668--daypart-demo-playground.us-east.modal.run
Member app at / and research console at /admin. No login. Synthetic data only: do not enter real health data. The app opens on a fictional member; "Start a fresh journal" gives an empty one. Journals are kept in memory and cleared after 60 minutes idle.
```

**Characters:** 317 / 1,024
**Ledger rows:** L43, L44, L1, L3, L12, L56
**Notes:** if the field takes a bare URL only, paste the first line (63 characters). Checked as a
judge would on 2026-11-10: reachable with no login, the journey passed 9 of 9 steps (L44). A
journal resets itself when it expires; a new one starts from the button above.

## Field 7: Deck

**Form input:** a file upload.

```text
Syntropy-FHDIC-deck.pdf (pending: built from deck-outline.md, at most 5 MB)
```

**Characters:** 75 / no limit
**Ledger rows:** none (P1)
**Notes:** the 8-slide [deck outline](deck-outline.md) is the source; UIUX builds the deck on its
own issue. The official template is not public (P1), so the deck claims no template compliance
until a person checks it. Upload only after the owner approves the deck.

## Field 8: Conflict of interest

**Form input:** a declaration per team member.

```text
Owner input required: each team member answers for each category the form lists. Agents do not answer this field.
```

**Characters:** 113 / no limit
**Ledger rows:** none (P4)
**Notes:** ask every member, per category. Never fill a default for anyone.

## Field 9: Software or hardware

**Form input:** a choice.

```text
Software
```

**Characters:** 8 / no limit
**Ledger rows:** L1, L55
**Notes:** the prototype is a hosted web app with no hardware component (L55).

## Field 10: Video link

**Form input:** a URL (optional).

```text
Pending: leave empty until the video is reviewed and the owner authorises a link.
```

**Characters:** 81 / no limit
**Ledger rows:** none (P3)
**Notes:** the video is built on its own issue from captures of this build. Paste a link only once
it works, has been reviewed, and the owner has approved publishing it. The organiser publishes no
video rule.

# Deck outline: 9 slides

The source for the FHDIC deck. UIUX builds the deck from this outline on its own issue; agents
publish and submit nothing. Each slide has **one message**, the [evidence ledger](evidence-ledger.md)
rows it may use (a number on a slide must come from one of them), and the UI screen or figure that
illustrates it. Screens are named by their route on the hosted build at 68236f1
([hosted probe](sources/hosted-probe-2026-11-10.md)): the member app at `/` and the research
console at `/admin`.

**Rules for every slide**
- The organiser's official template is not public (ledger P1). Adapt this outline to the template
  once a person has it; until then claim no template compliance.
- Large, high-contrast type and one message per slide. A chart states its units and its sample
  size.
- Footer on every slide: "Synthetic data and simulated results. Not medical advice. Not tested
  with people."
- Show only what the hosted build does. Anything not built is labelled *concept* or left out.
- Name no libraries, platforms or model names on a slide; they belong in the
  [technical appendix](technical-appendix.md).
- Export an editable source and a PDF of at most 5 MB.

## Slide 1: Problem and user

**Message:** Goals and barriers change week to week, and generic reminders do not show what they
know about you or why they suggest something.
**Ledger rows:** L37, L41, L71
**Illustration:** the member app's check-in screen (`/#today`, "What matters today?", personalised with the member's name) as a
quiet background, with the challenge name "[Wellness] Sustaining Healthy Behaviors" and the team
name *Syntropy*. The tagline may appear as the team's aim, in quotation marks, never as a result.
**Speaker note:** no statistic about the problem appears: the pack has no sourced figure for it.

## Slide 2: The experience

**Message:** Check in, review what the system understood, see it in your passport, and choose a
next step: nothing is saved until you confirm it.
**Ledger rows:** L5, L45, L49, L53, L55
**Illustration:** four screenshots in a row from the hosted build: `/#today` (check-in), `/#review`
(the three proposals from "slept 6 hours, pain 4/10, mood 3 out of 5, walked 8000 steps", each with
its snippet and method), `/#passport`, `/#next` (choose, defer, ask a professional). Voice and video
show as unavailable on the check-in screen; keep that visible.

## Slide 3: How it works

**Message:** One reproducible path: check-in, proposed values, your review, a scoped memory, the
passport and a bounded next step, each step leaving a trace.
**Ledger rows:** L6, L9, L10, L11, L24, L43
**Illustration:** a simplified version of the flow diagram in [architecture.md](architecture.md):
check-in → safety checks → proposals → review → memory (confirmed only) → passport and next step.
A second, separate lane: synthetic scenarios → evaluation → fine-tuning → frozen comparison. No
box for anything not built.

## Slide 4: Interpretability

**Message:** Every value shows where it came from, when, how sure the system is, and what it
withholds.
**Ledger rows:** L21, L22, L20, L50, L51, L54
**Illustration:** one passport card on `/#passport` with its evidence thread open (source check-in
→ saved observation → memory version → explanation and public source → safety check), beside the
withheld pain card ("Not enough data yet.", last value 16 days old) and the inventory's 5 gaps.
Show a reference range next to a value, with no high or low label.

## Slide 5: Learning and evidence

**Message:** Two fine-tuning stages ran and were compared with the base model on 141 held-out
synthetic prompts; the simulator compares scripted policies and a small learned policy. None of it
is a patient outcome.
**Ledger rows:** L57, L58, L59, L60, L61, L62, L63, L66, L79
**Illustration:** the research console's results screen (`/admin#lab`). A bar chart of boundary pass
rate, n = 141, base 45 of 141, fine-tuned 141 of 141, with the note that 90 of the base model's
replies were empty. Beside it, the weak slice: the lapse-recovery check passes on only 7 of 51
(and 6 of 51) check-in prompts. Label the GRPO stage "simulated: a small message-type policy, not a language model" (HAC-75).
Units and sample sizes on every axis.

## Slide 6: What helps this member

**Message:** Seven short questions, a reward model you can read term by term and a small learned
policy turn simulated answers into next steps, each with its reason. Synthetic only.
**Ledger rows:** L74, L75, L76, L77, L78, L79, L80, L81
**Illustration:** the passport's Inclinations section on `/#passport` (what weighs most, and the
next steps each linked to one of them with "Why:"), beside three facts: the questions recover
hidden traits 76–91% of the time (chance 17–33%); the reward model's top message type matches the
simulator's for 83% of held-out members, and it predicts no better than status alone, so its value
is the explanation; the learned policy reaches 0.840 mean simulated adherence against 0.833 for
the best scripted approach, 0 rule violations. Label it simulated: a message-type policy, not a
language model, CPU only.

## Slide 7: Responsible AI and limits

**Message:** The prototype refuses what it should not do, and shows you when it does.
**Ledger rows:** L47, L48, L56, L65, L73
**Illustration:** three real refusals from the hosted build: the crisis hand-off text, the
personal-data refusal ("looks like personal data"), and the server's refusal of real input (403,
12 open gates; there is no screen for it since HAC-76). Close with the limits: synthetic only, no diagnosis,
treatment or dosing, no clinical review, safety rules measured on a corpus, not proven.

## Slide 8: Feasibility and path to deployment

**Message:** It runs today as a hosted prototype; reaching people needs consent, privacy,
security, clinical oversight and a validation study first.
**Ledger rows:** L43, L44, L12, L33, L73
**Illustration:** the 12 governance gates as a checklist, all open, and the validation path from the
[technical appendix](technical-appendix.md#path-to-clinical-validation) as a short timeline of
*concept* steps (each marked not started). No cost or scale figure: none is measured (P9).

## Slide 9: Impact and next steps

**Message:** What it would take to show this helps people: a named clinical reviewer, a consented
pilot and a pre-registered measure.
**Ledger rows:** L58, L79, L73, L71
**Illustration:** the timeline screen (`/#timeline`, 28 check-ins) as the picture of a
longitudinal record, with the next steps as text: name a clinical reviewer, close the governance
gates, grow the learned policy beyond choosing a message type, run a consented pilot. Any impact statement is an
aim, never a result. Contact and link to the hosted prototype.

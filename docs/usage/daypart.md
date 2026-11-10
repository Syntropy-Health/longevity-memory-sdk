# daypart — usage

What you can do with the demo API (synthetic data only; not medical advice). Everything below is
live on the hosted demo (P1–P4 are deployed); you can also run it locally with `uv run daypart-demo serve`.

## Clinical Human Clone: check in and review (FHDIC P1)

1. **Start a journal** for a synthetic member: `POST /api/journals {"member_id": "syn-001"}`. Each
   visitor gets their own journal, kept in memory for up to 60 minutes idle.
2. **Check in**, in one of these ways:
   - text: `POST /api/checkins {"journal_id", "text": "slept 6 hours and walked 8000 steps"}`
   - a bundled demo file: list them with `GET /api/fixtures`, then send `{"journal_id", "fixture_id"}`
   - an upload of one of those same demo files (multipart `file` + `journal_id`). Any other file is refused.

   You get proposals back. **Nothing is saved yet.** Text that looks like personal data is refused
   whole. Crisis language gets a fixed message pointing to a person and to emergency services.
3. **Review** every proposal: `POST /api/checkins/{id}/review {"decisions": [...]}`, with one
   `confirm`, `correct`, `discard` or `save_unmapped` per proposal. A flagged proposal (an assumed
   unit, an ambiguous date, a contradiction…) must be corrected, discarded or saved as unmapped
   before it can be confirmed. An unknown word has nothing to correct it to: it can only be
   discarded or saved as unmapped. The review saves everything or nothing.
4. **Inspect** a saved value: `GET /api/journals/{journal_id}/observations/{record_id}` shows its
   code, LOINC version, source, method, quality and allowed use.

## Clinical Human Clone: passport, next step and lab (FHDIC P2)

5. **Passport**: `GET /api/journals/{journal_id}/passport?day=` lists one card per concept with its
   source, time, provenance, observed-or-simulated status and a five-step evidence thread. A sourced
   reference range sits beside a ready value, with its population and source; nothing is called high
   or low. `GET /api/inventory` lists the concepts and the gaps the passport does not cover.
6. **Next step**: `GET /api/journals/{journal_id}/next-step` suggests one step after a saved check-in
   (409 `no_saved_checkin` before any). `POST` the same path with `{"step_id", "choice"}`, where the
   choice is `choose`, `defer` or `ask_professional`; a stale step gets 422 `unknown_step`.
7. **Learning lab**: `GET /api/lab` returns the committed training and evaluation rows, each with
   its run ID, split, seed and failure count; GRPO is "proposed, not built".
8. `GET /api/units` lists the units a correction may use for each concept.

## Clinical Human Clone in the browser (FHDIC P3)

Run `uv run daypart-demo serve` from `engine/` (or open the hosted demo) and follow the journey:

1. **Check in** (`#checkin`, "What matters today?"): type a line, or pick a demo file or demo image. (The API also takes a multipart upload; it accepts only the allow-listed demo fixtures.)
2. **Review** (`#review`): confirm, correct, discard or save each proposal as unmapped. Nothing is
   saved until you finish the review. Crisis language shows a fixed hand-off notice instead.
3. **Passport** (`#passport`): one card per measure, with its evidence thread. A sourced reference
   range sits beside a recent value, with its population and source link; it is never used to
   call the value high or low. `#passport/inventory` lists what is covered and what is not.
4. **Next step** (`#next`): one suggestion; choose it, put it off, or ask a professional.
5. **Learning lab** (`#lab`): the base, sft and dpo models and the 3 baselines, from the committed
   results.

The **research view** (`#research`) keeps the earlier playground. The full Streamlit results page is
`uv run daypart-demo dashboard` ("Clinical Human Clone: research view").

## Real input

`GET /api/mode` shows that real input is off, along with the 12 open governance gates. Turning it on
through the API, the UI or `DAYPART_REAL_INPUT=1` is always refused in this build. See
`docs/daypart/real-input-pathway.md`.

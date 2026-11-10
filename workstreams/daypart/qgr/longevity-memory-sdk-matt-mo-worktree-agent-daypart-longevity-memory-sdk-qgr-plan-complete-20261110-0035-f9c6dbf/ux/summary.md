# UX review — daypart/hac-fhdic-build @ ae86824
reviewed: head ae86824b5fdb542254e681c5f9a292d27b5bf1fd tree d8033e7de232e619df4c03a3bf26925ce26503ec
ux verdict: user-facing (default globs (user_facing_paths unset); base origin/main)
config: none (Python Playwright project; no playwright.config.* by design) — engine/tests/ui/test_journey_a11y.py + smoke script driving the in-process FastAPI app (engine/daypart/demo/app.py create_app, uvicorn on 127.0.0.1 ephemeral port, throwaway)
viewports: 1280x800, 375x812 (A&D SC6 mandates 375 px; used instead of the skill default 390x844)
trace: not recorded (Python Playwright smoke; no trace.zip). Scratch worktree stamp matched the reviewed tree.

Acceptance source: workstreams/daypart/AND.md SC1, SC6, SC8, §4.10, Failure handling (crisis row). Every row also asserts h1 focus on route change (navigation by clicking nav or links, not page.goto), axe-core 4.x vendored (WCAG 2.0/2.1 A+AA) 0 serious/critical, scrollWidth <= clientWidth, no pageerror and no console error.

| # | Acceptance (verbatim / spec ref) | Spec | Result | Screenshots |
|---|---|---|---|---|
| 1 | SC1: a judge completes check in → … (check-in screen, banner, real-data warning) | .ux-smoke/smoke.py step 01 | pass | 01-checkin-desktop.png, 01-checkin-mobile.png |
| 2 | SC1 … → review ("Review before saving", proposal rows) | smoke.py step 02 | pass | 02-review-desktop.png, 02-review-mobile.png |
| 3 | SC9: nothing saved until review completes; confirm all → saved | smoke.py step 03 | pass | 03-review-saved-desktop.png, 03-review-saved-mobile.png |
| 4 | SC1 … → passport; AM-1: sourced reference range beside a ready value with population + source link, never called high/low; review label "Reviewed (board sign-off, 7 Nov 2026)"; evidence thread opens | smoke.py step 04 | pass | 04-passport-desktop.png, 04-passport-mobile.png, 04b-passport-range-card-desktop.png, 04b-passport-range-card-mobile.png |
| 5 | SC1 … → next step (Choose / Defer / Ask a professional) | smoke.py step 05 | pass | 05-next-desktop.png, 05-next-mobile.png |
| 6 | SC1 … → lab ("Simulated outcomes are not patient outcomes", GRPO "proposed, not built") | smoke.py step 06 | pass | 06-lab-desktop.png, 06-lab-mobile.png |
| 7 | §4.10: #research labelled "Research view (optional)"; episode start + step | smoke.py step 07 | pass | 07-research-desktop.png, 07-research-mobile.png |
| 8 | SC8: enabling real input via UI, API or config is refused with the open gates listed (UI: 12 gates in aria-live panel; API POST /api/mode → 403 real_input_refused + open_gates; DAYPART_REAL_INPUT=1 → GET /api/mode enabled:false, requested:true, 12 gates) | smoke.py step 08 | pass | 08-real-input-refused-desktop.png, 08-real-input-refused-mobile.png |
| 9 | Failure handling: crisis language → fixed clinician_handoff in place of review, nothing saved | smoke.py step 09 | pass | 09-crisis-handoff-desktop.png, 09-crisis-handoff-mobile.png |

Existing specs run: engine/tests/ui (DAYPART_UI_REQUIRED=1 uv run pytest -q tests/ui) — 26/26 passed
Notes (not findings): the designed 403 refusal from POST /api/mode makes Chromium log a native "Failed to load resource" console line; this is expected for the refusal and is not an app error.
Findings: 0

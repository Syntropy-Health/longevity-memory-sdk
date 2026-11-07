# UX review — HAC-38 P3.1 (detached HEAD) @ 44764dc
reviewed: head 44764dc20ac174a95d8f71d93615aee097cdc8f9 tree 46be4e476c02019d0f161b51c02fb2e78e3e006c
ux verdict: user-facing (default globs (user_facing_paths unset); base 179d67d) — engine/daypart/demo/static/index.html changed
config: none in repo (no playwright.config.*). Ran a playwright-core script (smoke.js.txt) against a throwaway local uvicorn
  (`daypart.demo.app:create_app`, port 8765, booted from the scratch worktree; served index.html byte-identical to the scratch tree).
viewports: 1280x800 (desktop), 375x812 (mobile, per the HAC-38 375 px acceptance line)
trace: none (no test runner, so no trace.zip). Raw check output: results.json
scratch worktree matched the reviewed tree stamp (46be4e4…)

| # | Acceptance (verbatim) | Spec | Result | Screenshots |
|---|---|---|---|---|
| 1 | banner on every route | smoke.js journey() screen() | pass: `.banner` first in body, outside main, role=status, visible on #checkin #review #passport #next #lab #research | 01-checkin-desktop.png, 01-checkin-mobile.png … 08-research-*.png |
| 2 | journey works end to end | smoke.js journey() (real backend) | pass: "slept 6 hours and walked 8000 steps" → #review (2 proposals) → Save → "Saved 2 values" → #passport (Sleep 6 h, Step count 8000 ready) → #next → Choose → "Goal set" → #lab → #research | 02-review-*.png, 03-review-saved-*.png, 04-passport-*.png, 05-next-*.png, 06-next-chosen-*.png, 07-lab-*.png |
| 3 | axe 0 violations per screen | smoke.js axeRun (wcag2a/aa, 21a/aa, best-practice) | pass: 0 on all 6 routes and all 8 rev-2 states, both viewports | all *.png |
| 4 | no horizontal scroll at 375 px | smoke.js screen() scrollWidth + overflowing-element scan | pass: scrollWidth 375 everywhere | *-mobile.png |
| 5 | keyboard focus visible and h1 focused on route change | smoke.js focusWalk + screen() | pass with finding UX-1: every Tab stop (16 on #checkin, review radios + submit) has a ring; h1 focused on every in-app route change; NOT on direct load of a hash URL | 01-checkin-*.png, 02-review-*.png |
| 6 | ranges show no interpretation words | smoke.js states() ranges | pass: real NHLBI "7–9 h / adults" row and mocked shown/one-sided/none/withheld; no high/low/normal/within/above/below; withheld = no row; value style identical across cards | 04-passport-*.png, 11-ranges-desktop.png, 11-ranges-mobile.png |
| 7 | review label never "clinically reviewed"/"vetted" | smoke.js states() reviewLabel | pass: last #pp-meta row "Review = Reviewed (board sign-off, 7 Nov 2026)", once; odd shape rendered verbatim as text; suppressed copy "No reviewed source applies…"; no clinically reviewed/vetted/approved/validated on page | 12-review-label-desktop.png, 12-review-label-mobile.png |
| 8 | §3.1.1 crisis hand-off (real crisis marker "crisis line") | states() handoff | pass: ink notice, role=alert, tabindex=-1, focused, server text verbatim, intro/warning/form hidden, textarea cleared, no links/phone, one secondary button; button restores form, focus to textarea | 10-handoff-desktop.png, 10-handoff-mobile.png |
| 9 | §3.4.1 409 Check in first | states() next409 (real backend) + POST mock | pass: GET: info notice, no role, focus on h1, primary href #checkin; POST: role=alert, focused | 13-next-409-desktop.png, 13-next-409-mobile.png |
| 10 | §3.4.2 422 unknown_step | states() next422 (mock) | pass: old panel aria-busy + 3 aria-disabled during re-GET; new step shown; info notice role=alert focused above panel; 1 POST only (no auto re-send); no error body | 14-next-422-desktop.png, 14-next-422-mobile.png |
| 11 | §3.8 5xx GET | states() pp503 | pass: notice under h1, body hidden, focus stays on h1, "(error 503)", no body leak, Try again re-GETs | 15-passport-503-desktop.png, 15-passport-503-mobile.png |
| 12 | §3.8 5xx POST + §3.1 extractor_output_invalid | states() ci503 | pass: form + text kept, notice focused with 3 px ring, Try again re-POSTs; extractor copy correct, no aria-invalid | 16-checkin-503-desktop.png, 16-checkin-503-mobile.png |
| 13 | §3.8 network failure | states() labNet | pass: "We could not reach the demo server…", body hidden, focus on h1 | 17-lab-network-desktop.png, 17-lab-network-mobile.png |

Existing specs run: none (repo has no Playwright specs/config) — 0/0
Console: no page errors; only expected "Failed to load resource" lines for the mocked 409/422/5xx/abort responses.

Findings: 3

1. **[MEDIUM] UX-1** `#checkin` `#passport` `#next` `#lab` `#research` (direct load / reload) @ both — on first load of any hash URL focus ends on `<body>`, not the h1. route() focuses the h1, then Chrome's load-time scroll-to-fragment (section ids equal the route names, e.g. `<section id="checkin">`) drops it. Loading `/` with no hash keeps focus on the h1, and in-app route changes are fine.
   - Evidence: 01-checkin-desktop.png, 01-checkin-mobile.png; results.json journey.*.initialLoadFocus = "BODY"
   - Recommendation: rename the section ids (e.g. `screen-checkin`) so the fragment matches no element, or run the initial focus after load (requestAnimationFrame / `load` event).
2. **[LOW] UX-2** `#passport` @ both — values print raw: "Pattern score 57.14285714285714 score" and "Simulated record 0 1" (UCUM dimensionless unit "1" shown as a unit). fmtNum/fmtUnit are new in this diff.
   - Evidence: 04-passport-mobile.png, 04-passport-desktop.png
   - Recommendation: round for display (keep the full value in the evidence thread) and hide unit "1".
3. **[INFO] UX-3** repo-wide — there is no Playwright config or e2e spec, so this pass ran a standalone playwright-core script instead of `npx playwright test`, and produced no trace.zip. Under review-ux §3.1 read literally, a missing config is CRITICAL. The orchestrator chose this script approach, so the gate owner decides how to treat it.
   - Evidence: smoke.js.txt

# UX review — daypart/hac-fhdic-build @ 3ead811
reviewed: head 3ead81108568c9ba9c82b762e728198a3f4ac69d tree a6b01efbaefc263cca2d871ae5b111534cbaa66e
ux verdict: user-facing (default globs (user_facing_paths unset); changed files under engine/tests/ui/; base ada2950)
config: engine/tests/ui/test_journey_a11y.py (Python Playwright; no playwright.config — app booted in-process by uvicorn on 127.0.0.1:<free port>, throwaway instance)   viewports: 1280x800, 375x812 (375 per caller / suite MOBILE; skill default 390x844)
trace: trace.zip sha256 261b0eb7d178bbd1d13ed96f2671ab551abe909dfe995b5903f6668ff4a746a8 (last test: #research @ 375; kept in UX_DIR, not attached)
acceptance: from caller (HAC-38 P3.2) — one smoke per route #checkin #review #passport #next #lab #research; UI unchanged since ada2950

| # | Acceptance | Spec | Result | Screenshots |
|---|---|---|---|---|
| 1 | Given a direct load of `#checkin` When the screen renders Then its h1 has focus and axe (WCAG 2.0/2.1 A+AA) reports 0 violations | .ux-smoke/smoke.py (route checkin) | pass — desktop: h1 'What matters today?' focused=True, axe=0, hscroll=False; mobile: h1 'What matters today?' focused=True, axe=0, hscroll=False | 01-checkin-desktop.png, 01-checkin-mobile.png |
| 2 | Given a direct load of `#review` When the screen renders Then its h1 has focus and axe (WCAG 2.0/2.1 A+AA) reports 0 violations | .ux-smoke/smoke.py (route review) | pass — desktop: h1 'Review before saving' focused=True, axe=0, hscroll=False; mobile: h1 'Review before saving' focused=True, axe=0, hscroll=False | 02-review-desktop.png, 02-review-mobile.png |
| 3 | Given a direct load of `#passport` When the screen renders Then its h1 has focus and axe (WCAG 2.0/2.1 A+AA) reports 0 violations | .ux-smoke/smoke.py (route passport) | pass — desktop: h1 'Health Clone Passport' focused=True, axe=0, hscroll=False; mobile: h1 'Health Clone Passport' focused=True, axe=0, hscroll=False | 03-passport-desktop.png, 03-passport-mobile.png |
| 4 | Given a direct load of `#next` When the screen renders Then its h1 has focus and axe (WCAG 2.0/2.1 A+AA) reports 0 violations | .ux-smoke/smoke.py (route next) | pass — desktop: h1 'Suggested next step' focused=True, axe=0, hscroll=False; mobile: h1 'Suggested next step' focused=True, axe=0, hscroll=False | 04-next-desktop.png, 04-next-mobile.png |
| 5 | Given a direct load of `#lab` When the screen renders Then its h1 has focus and axe (WCAG 2.0/2.1 A+AA) reports 0 violations | .ux-smoke/smoke.py (route lab) | pass — desktop: h1 'Learning lab' focused=True, axe=0, hscroll=False; mobile: h1 'Learning lab' focused=True, axe=0, hscroll=False | 05-lab-desktop.png, 05-lab-mobile.png |
| 6 | Given a direct load of `#research` When the screen renders Then its h1 has focus and axe (WCAG 2.0/2.1 A+AA) reports 0 violations | .ux-smoke/smoke.py (route research) | pass — desktop: h1 'Research view (optional)' focused=True, axe=0, hscroll=False; mobile: h1 'Research view (optional)' focused=True, axe=0, hscroll=False | 06-research-desktop.png, 06-research-mobile.png |

Smoke notes: axe counted ALL impacts (stricter than the suite's serious/critical filter): 0 on every route at both widths. No uncaught page errors; no horizontal scroll at either width. Screenshots are full-page, direct-load (empty journal) state.

Existing specs run: engine/tests/ui/test_journey_a11y.py (whole module, DAYPART_UI_REQUIRED=1, chrome-headless-shell 1248 arm64) — 14/14 passed in 7.68s

Findings: 1
1. **[INFO]** `#next` @ 1280 and 375 — direct load with no saved check-in logs a console error "Failed to load resource: 409 (Conflict)"; the page correctly renders the "Check in first" notice with a Go to check-in action (designed empty state, h1 focused, axe 0). Evidence: 04-next-desktop.png, 04-next-mobile.png. Recommendation: none required; optionally pre-check journal state client-side to avoid the noisy 409 in devtools.

# UX review — daypart/hac-fhdic-build @ 62967a6
reviewed: head 62967a621ec85c7d15ec6c91aca81803e7c3ed0a tree 222408a672c499c7f4e67dd75768e3c6ba64171a
ux verdict: user-facing (default globs (user_facing_paths unset); base 5a79ef1c92a65a2d0933ccc79e58716212aab9e4)
config: none (Python project; Python Playwright from the engine `ui` group, app booted in-process by uvicorn on 127.0.0.1:<free port>, as tests/ui/test_journey_a11y.py does)   viewports: 1280x900, 375x812
trace: trace.zip sha256 849e066b233c740a8b7f60087e675aa097b53a918e8c7967d7e6e677840c551a (kept in UX_DIR, not attached; desktop run)

Acceptance lines come from the caller (HAC-38 P6.2 brief). Spec: generated `.ux-smoke/smoke.py` (scratch, deleted after the run). Each route was also checked for: axe (wcag2a/aa, 21a/aa) serious+critical = 0, scrollWidth <= clientWidth, focus on the screen h1 after the route change (nav click, direct load for /admin and /admin/lab), 12 Tab stops each with a visible outline/box-shadow, and with prefers-reduced-motion: reduce, every element/pseudo has animation+transition duration and delay 0 and no running Animation with duration > 0.

| # | Acceptance (verbatim) | Spec | Result | Screenshots |
|---|---|---|---|---|
| 1 | Member `/`: #today with the persona (name in h1, aside stats) | smoke.py run() 01 | pass: h1 "What matters today, Rowan?", aside 28 days / 28 check-ins / 86 observations / 9 cards | 01-today-desktop.png, 01-today-mobile.png |
| 2 | #review | smoke.py 02 | pass: 2 proposal cards | 02-review-desktop.png, 02-review-mobile.png |
| 3 | then save → "Your clone updated" (focus on the panel, rows from the timeline) | smoke.py 03 + post-save focus check | pass: focus on div.clone-updated with 3px solid ring; rows (observed + 2 updated) match this save's GET /api/journals/{id}/timeline entry | 03-clone-updated-desktop.png, 03-clone-updated-mobile.png |
| 4 | #passport | smoke.py 04 | pass | 04-passport-desktop.png, 04-passport-mobile.png |
| 5 | #next (Choose → View timeline) | smoke.py 05 | pass: "Goal set … View timeline" link reaches #timeline | 05-next-*.png, 05b-next-chosen-desktop.png, 05b-next-chosen-mobile.png |
| 6 | #timeline (newest open, Show earlier days) | smoke.py 06 | pass: first entry open; Show earlier days 8 → 15 entries, focus moves to the first new day; axe and reflow clean after | 06-timeline-*.png, 06b-timeline-earlier-desktop.png, 06b-timeline-earlier-mobile.png |
| 7 | The member page has no /admin link | smoke.py 01 | pass: no a[href*=admin] (the only "/admin" text is an HTML comment) | 01-today-desktop.png, 01-today-mobile.png |
| 8 | Console `/admin`: #pipeline (KPIs and 2 lanes with real numbers) | smoke.py 07 | pass: KPIs 1.000 / 0.645 / ✓ passed / 0.833, all equal to GET /api/lab; live + offline lanes visible, offline rows carry the lab's numbers | 07-pipeline-desktop.png, 07-pipeline-mobile.png |
| 9 | #lab | smoke.py 08 | pass | 08-lab-desktop.png, 08-lab-mobile.png |
| 10 | #inventory | smoke.py 09 | pass | 09-inventory-desktop.png, 09-inventory-mobile.png |
| 11 | #playground | smoke.py 10 | pass (episode started, one step) | 10-playground-desktop.png, 10-playground-mobile.png |
| 12 | #input (403 + 12 gates) | smoke.py 11 | pass: POST /api/mode 403, 12 gates listed | 11-input-desktop.png, 11-input-mobile.png |
| 13 | `/admin/lab` resolves | smoke.py 12 | pass: lab screen, URL rewritten to /admin#lab, h1 focused | 12-admin-lab-path-desktop.png, 12-admin-lab-path-mobile.png |
| 14 | On every route: axe 0 serious/critical, no sideways scroll, h1 focused after a route change, visible focus on Tab stops, reduced motion → no animation/transition above 0 | smoke.py common() + reduced-motion pass | pass on all 12 screens x 2 viewports (incl. the clone-updated moment) | all of the above |

Console: one expected `Failed to load resource: 403` per run (the #input POST /api/mode refusal). No pageerror.

Existing specs run: engine/tests/ui/test_journey_a11y.py — 49/49 passed

Findings: 1
1. LOW `/#today` @ 375x812 — a wrapped `.tag` chip ("Updated: Sleep duration (hours)") in the "Your clone" Latest update list sets two lines at line-height 1 with 0 vertical padding, so the text crowds the pill border. Evidence: 01c-today-latest-chip-mobile.png, 01-today-mobile.png. Fix: `.tag` line-height ~1.25 and a small block padding (or white-space:nowrap with text-overflow on narrow screens); index.html:113-114.

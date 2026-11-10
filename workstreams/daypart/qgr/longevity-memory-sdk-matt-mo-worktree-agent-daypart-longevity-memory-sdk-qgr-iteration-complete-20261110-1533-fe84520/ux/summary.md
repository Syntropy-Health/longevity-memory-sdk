# UX review — daypart/hac-fhdic-build @ b2f3ace
reviewed: head b2f3aceb4f0419b042e0068c1ce75d46c0978963 tree 7375246aa56795ffa9b49fdbd9ce63802c6da152
ux verdict: user-facing (default globs (user_facing_paths unset); base dbe19da3a502fa449aecfa4ae9aeac83a0bb3b4a)
config: none (Python Playwright project; caller-directed harness: engine/tests/ui/test_journey_a11y.py + .ux-smoke/smoke.py serving create_app() via uvicorn on an ephemeral port)   viewports: 1280x800, 375x812
trace: not captured (Python harness, no Playwright trace; throwaway in-process instance only)
acceptance: CTO AM-2, P6.1 (7 lines, from caller)

Per row, per viewport, the smoke also checks: axe (vendored axe.min.js, WCAG 2.0/2.1 A+AA) 0 serious/critical, no horizontal scroll, h1 focus after nav-link route change, no page errors, none of the removed tags.

| # | Acceptance (verbatim) | Spec | Result | Screenshots |
|---|---|---|---|---|
| 1 | member app at / opens on the seeded fictional persona's journal (passport shows member "Rowan Ellis" and many observed ready cards) | .ux-smoke/smoke.py::row1 | pass (Member = Rowan Ellis; 7 observed ready cards at both viewports) | 01-persona-journal-desktop.png, 01-persona-journal-mobile.png |
| 2 | no screen on either surface shows "Demo mode", "Synthetic data only", "Not for clinical use", "Research view (optional)" or a banner | .ux-smoke/smoke.py::row2 | pass (/#checkin,#review,#passport,#next; /admin#lab,#inventory,#research) | 02-no-tags-desktop.png, 02-no-tags-mobile.png |
| 3 | member nav = Check in, Review, Passport, Next step and no member link goes to /admin, #lab, #research or #inventory (evidence thread simulated/learning links render as text) | .ux-smoke/smoke.py::row3 | pass (all threads opened; 0 admin hrefs; 19 simulated/learning thread steps, 0 anchors) | 03-member-nav-desktop.png, 03-member-nav-mobile.png |
| 4 | research console /admin shows Learning lab, Inventory, Playground nav, links back to /, and the Real input control refuses with 12 gates; member app has no Real input control | .ux-smoke/smoke.py::row4 (+row3 for member #ri-btn absence) | pass (12 gates, refusal title shown, #ri-btn count 0 on /) | 04-admin-console-desktop.png, 04-admin-console-mobile.png |
| 5 | "Start a fresh journal" gives an empty journal: #next shows "Check in first" | .ux-smoke/smoke.py::row5 | pass | 05-fresh-journal-desktop.png, 05-fresh-journal-mobile.png |
| 6 | check-in → review → save → passport → next step still works on the persona journal | .ux-smoke/smoke.py::row6 | pass (Rowan Ellis kept after save; "Goal set") | 06-journey-desktop.png, 06-journey-mobile.png |
| 7 | GET /api/journals/{id}/timeline for the persona journal returns 28 entries (API check) | .ux-smoke/smoke.py::row7 | pass (persona-v1, 200, 28 entries) | 07-timeline-api-desktop.png, 07-timeline-api-mobile.png |

Existing specs run: engine/tests/ui/test_journey_a11y.py — 25/26 first run (test_t10_2_keyboard_only_journey failed); keyboard test alone rerun 4x: 3 pass, 1 fail (flaky, ~2/5)
Out of scope (P6.2, not flagged): visual overhaul, timeline view in the member UI.
Findings: 2

Re-verified after the QG fixes at e1e4859: engine/tests/ui 26/26 passed; test_t10_2_keyboard_only_journey 12/12 after K4 (stale-render guard + hidden reload). Findings above: U1 fixed as K4; U2 deferred (registry allowed_use, G32).

# Judge-path check (HAC-77), 2026-11-11

I opened the deck PDF's links and the demo link the way a logged-out judge would: a fresh browser
context with no cookies and no login, at 1280×720 and at 375×812. Hosted build: `daypart/build`
`4ba3adb28a44940b66cb6e3c9d62e7fa76e1df2f` (HAC-75 and HAC-76 merged). CI run 42942366810
deployed it after every gate job and deploy-demo passed. The served OpenAPI description is the
HAC-76 text ("training results, health areas, coaching sessions … Real input is off in this
build").

## Deck PDF links

| link (slide 9) | result |
|---|---|
| https://supermomo668--daypart-demo-playground.us-east.modal.run/ | 200, the member app, no login |
| https://github.com/Syntropy-Health/longevity-memory-sdk | 200, public repository |

The PDF has 9 pages and exactly these 2 URI links. `/admin` (the research console) also returns
200 when logged out.

## Demo, full journey

`capture/capture.js` ran the whole journey at each width as one real take. Its API logs are in
[`capture/clips-1280.json`](capture/clips-1280.json) and [`capture/clips-375.json`](capture/clips-375.json).

| step | 1280 | 375 |
|---|---|---|
| Check-in "slept 6 hours, pain 4/10, mood 3 out of 5, walked 8000 steps" | 201, 3 proposals | 201, review shown |
| Review: sleep corrected to 6.5 h, the other two confirmed, saved | 200 | 200 |
| Passport, evidence thread opened, withheld card | 200 | 200 |
| Passport Inclinations: 3 drivers, 3 next steps, each linked with "Why:" | shown | shown |
| Next step, Choose | 200 | 200 |
| Personal-data check-in (fictional name and e-mail) | **422**, the expected refusal; nothing saved | **422** |
| Crisis check-in "Can you give me a crisis line to call?" | 200, hand-off; nothing saved | 200, hand-off |
| Timeline | 200 | 200 |
| Research console: Overview, then Results (incl. the learned-policy row, 84.0%) | 200 | 200 |

The only status of 400 or above in either take is the expected 422 refusal. No page errors.

**No "Real input" screen** (HAC-76): there is no nav item for it. `GET /admin/input` returns 404,
and `/admin#input` falls back to the Overview. The server still refuses real input when asked
directly: `POST /api/mode` returns 403 `build_disallowed`, with 12 of 12 gates open.

A separate fresh-context pass checked every screen at both widths: `/#today`, `/#passport`,
`/#next`, `/#timeline`, `/admin/pipeline`, `/admin/lab`, `/admin/inventory`, `/admin/sessions`
and `/admin#input`. On each one `scrollWidth` equals the viewport, so there is no horizontal scroll
at 375. That pass saw 0 page errors and 0 responses of 400 or above.

## UI issues seen

None that block. The two HAC-65 items (mid-word breaks in the lab table, and the overrun in the
real-input gate list) are gone: HAC-76 fixed the table wrapping and removed the gate-list screen.

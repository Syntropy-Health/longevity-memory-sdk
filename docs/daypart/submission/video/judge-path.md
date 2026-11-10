# Judge-path check (HAC-65), 2026-11-10

I opened the deck PDF's links and the demo link as a logged-out judge would: a fresh browser
context with no cookies and no login, at 1280×720 and 375×812. Hosted build: `daypart/build`
`e50ebb71aaeb7b61a42cd81c7481e1a17e49fe98`, deployed by CI run 42901423198 (all gate jobs and
deploy-demo green). Its app code under `engine/daypart` is the same as 68236f1, the build the pack
probed.

## Deck PDF links

| link (slide 8) | result |
|---|---|
| https://supermomo668--daypart-demo-playground.us-east.modal.run/ | 200, member app, no login |
| https://github.com/Syntropy-Health/longevity-memory-sdk | 200, public repository |

The PDF has exactly these 2 URI links. `/admin` (research console) also returns 200 logged out.

## Demo, full journey

`capture/capture.js` ran the whole journey at each width as one real take. Its API log is in
[`capture/clips-1280.json`](capture/clips-1280.json) and [`capture/clips-375.json`](capture/clips-375.json).

| step | 1280 | 375 |
|---|---|---|
| Check-in "slept 6 hours, pain 4/10, mood 3 out of 5, walked 8000 steps" | 201, 3 proposals | 201, review shown |
| Review: sleep corrected to 6.5 h, two confirmed, saved | 200 | 200 |
| Passport, evidence thread opened | 200 | 200 |
| Next step, Choose | 200 ("Goal set") | 200 |
| Crisis check-in "Can you give me a crisis line to call?" | 200 hand-off, nothing saved | 200 hand-off |
| Timeline | 200 | 200 |
| Research console: pipeline, learning lab | 200 | 200 |
| Real input requested | **403** (expected refusal, 12 of 12 gates open) | **403** |

The only status of 400 or above on either take is the expected 403 refusal. No page errors.
Separately, the personal-data refusal (fictional e-mail and name) returned 422, and nothing was saved.

On every screen (`/#today`, `/#passport`, `/#next`, `/#timeline`, `/admin/pipeline`, `/admin/lab`,
`/admin/inventory`, `/admin/playground`, `/admin/input`), `scrollWidth` equals the viewport at
both widths: no horizontal scroll at 375.

## UI issues seen (not fixed here; for the `daypart/build` owner)

- **Learning lab table at 1280:** the narrow Seed and Failures columns still break words
  mid-word ("cohor/t", "degenerat/e"). It is legible on camera. The deck redraws these numbers as
  a chart instead of showing the table.
- **Real-input gate list at 1280:** in the two-column list, a long item in column 1 runs into
  column 2 ("… · open8. Terms …", "… · open9. Review …"). It is visible in the video's real-input
  segment and on slide 6. It is cosmetic, and the text stays readable.

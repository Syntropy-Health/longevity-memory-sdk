# UX review — daypart/hac75-rm-grpo @ 71644b0
reviewed: head 71644b00946f9e742f2d6713e8b4b8659c439c39 tree 8f1c56643e61842c42bd41f3655802317185ddf3
ux verdict: user-facing (default globs (user_facing_paths unset); base origin/daypart/build)
config: none (Python pytest-playwright; engine/tests/ui/test_journey_a11y.py, in-process uvicorn on create_app())   viewports: 1280x800, 375x812
trace: trace.zip sha256 3b873115323aaa5a8893e467927dac47f492065f43f6bf18d14d61cfa2264a4e (kept in UX_DIR, not attached)

Scratch worktree /tmp/rev-ux matched the reviewed tree (8f1c566). The live tree was not touched.
Environment: chromium headless shell 1248 ran with system libs from /tmp/chrdeps (LD_LIBRARY_PATH) and a
scratch FONTCONFIG_FILE. Without fonts every text box has 0 height and Playwright reports headings "hidden".
That is an environment artifact, not a product bug. CI demo-ui (run 42924627497) also passed on 71644b0.
The repo has no Playwright config (Python Playwright), so the smoke specs were one pytest module
(.ux-smoke/test_ux_smoke.py, run once, headless, tracing per context) and not a ux.config.ts.

| # | Acceptance (verbatim) | Spec | Result | Screenshots |
|---|---|---|---|---|
| 1 | #passport shows an "Inclinations" heading, a "What weighs most" list of drivers with Helps / Makes it harder tags, and 1–3 "Next steps" cards, each with an action, a "Why:" reason and "Linked to: <driver label>" | test_ux_smoke.py::test_01_passport_inclinations | pass (3 drivers, 3 cards, every Linked-to label matches a driver; no h-scroll; axe clean) | 01-passport-inclinations-desktop.png, 01-passport-inclinations-mobile.png (+ 01-…-section-*.png) |
| 2 | the inclinations text contains no engineering jargon (logit, reward, GRPO, model, feature, intent) | test_ux_smoke.py::test_02_inclinations_no_jargon | pass (whole-word, case-insensitive scan of #pp-incl, plurals included) | 02-inclinations-no-jargon-desktop.png, 02-inclinations-no-jargon-mobile.png |
| 3 | /admin#lab shows a GRPO row with mean adherence and violation rate, not "proposed, not built" | test_ux_smoke.py::test_03_admin_lab_grpo_policy | pass (lab: mean adherence 0.84, violation rate 0; pipeline GRPO stage: adherence 0.840, violations 0.000, episodes 150, no "proposed" tag) | 03-admin-lab-grpo-desktop.png, 03-admin-lab-grpo-mobile.png (+ 03-admin-pipeline-grpo-*.png) |

axe-core (vendored, wcag2a/aa + wcag21a/aa) found 0 violations of any impact on /#passport, /admin#lab and /admin#pipeline at both viewports.
There were no page errors and no console errors.

Existing specs run: tests/ui/test_journey_a11y.py -k "passport or pipeline or lab or every_route or console_routes or t8_4"
(test_every_route_no_tags_axe_and_reflow, test_t8_4_lab_says_simulated_not_patient_outcomes,
test_passport_range_rows_and_review_label_match_the_api, test_lab_request_times_out_at_15_s,
test_lab_failure_after_a_good_load_hides_the_table, test_rev3_console_routes_axe_reflow_focus_and_rings,
test_rev3_pipeline_shows_the_real_lab_numbers, test_rev3_pipeline_mocked_lab_mismatch_and_nulls,
test_rev3_pipeline_failed_lab_keeps_the_live_lane, test_rev3_pipeline_layout_vertical_below_72rem_horizontal_from_72rem,
+ param/other matches) — 14/14 passed

Findings: 3

1. **[MEDIUM]** `/#passport` @ 375 and 1280: driver labels written as barriers carry the opposite tag. "Forgetting is what most often gets in the way" shows "▲ Helps · weighs strongly", and "Weekends are harder for you" shows "▲ Helps · weighs moderately". The tag is the sign of the model term (daypart/rm/inclinations.py:233), but a member reads it as "forgetting helps me". All acceptance lines pass. This is a comprehension problem.
   - Evidence: ux/01-passport-inclinations-section-mobile.png | .ux-smoke/test_ux_smoke.py:83
   - Recommendation: write the tag about what the driver does to the routine, or reword the labels and tags so they agree (for example "Reminders help you" with "▲ Helps"). Add a unit check that a barrier-phrased label never gets "helps".
2. **[LOW]** `/#passport` @ 375 and 1280: every "Why:" reason repeats the same sentence ("…this kind of message was linked to a clear gain in days with the routine kept, on days when it was slipping"). Three cards read as boilerplate, and "this kind of message" is system-voice.
   - Evidence: ux/01-passport-inclinations-section-desktop.png
   - Recommendation: give each next step its own reason, or state the shared evidence once above the cards.
3. **[INFO]** `/admin#lab` @ 375: the stacked table's "Runs" caption wraps one letter per line. This was already there before this change: neither the caption nor table.stack is in the diff.
   - Evidence: ux/03-admin-lab-grpo-mobile.png
   - Recommendation: follow-up only. Give the stacked caption display:block or full width.

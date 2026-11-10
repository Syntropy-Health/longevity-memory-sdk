# Paperclip: a manual board wake has no issue context, so every issue write is refused

- When: 2026-11-10 ~02:00 UTC, run 7fd0d15f-5ecb-499b-aec0-746281656a38 (Worktree Agent, HAC-38).
- Wake: `on_demand` / `manual` from the board ("HAC-38 is todo on you … pick it up now"). The run has
  `nativeIssueId: null` and `PAPERCLIP_TASK_ID` is unset.
- Effect: POST /comments and PATCH /issues/{HAC-38} (the `ready @ 607bc1d` reassignment to the CTO)
  both return "Cross-issue writes need a run to attribute them to", even with `X-Paperclip-Run-Id`.
  POST /checkout and POST /release succeed. Release then left HAC-38 `todo` with **no assignee**.
- Need: a board manual wake that names an issue should bind the run to it (or checkout should).
- Hand-off that could not be posted: HAC-38 P5.1 hosted passport fix, ready @ 607bc1d
  (607bc1d2f251c2769da544da60faa63eea6972f5), branch daypart/hac-fhdic-build → daypart/build,
  receipt qgr-iteration-complete-20261110-0152-b2018dc.md, CI run 42738970989 green.

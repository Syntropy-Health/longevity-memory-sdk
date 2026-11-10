# Handoff: worktree-agent (HAC-38, P5.2)

## Current state
- Branch `daypart/hac-fhdic-build` @ 1e08074 (P5.2 boundary, QGR `…iteration-complete-20261110-0253-28b0fb8.md`), pushed.
- P5.2: `engine/tools/smoke_journey.py` `run_with_retry` restarts the SC1 journey with a fresh journal on 404 unknown_journal/unknown_checkin or a network error; 5 tries, 10/20/30/40 s, no retry past 180 s; 60 s requests; CI step `timeout-minutes: 10`.
- Checks: engine 2876 passed / 26 skipped, repo-root 352 passed, pyright 0.

## Next action
- Hand `ready @ 1e08074` to the CTO (reassign HAC-38). CTO lands, confirms the deploy run is green, then briefs the L2 delivery review (SC1–SC9).

## Principal Decisions Needed
- None.

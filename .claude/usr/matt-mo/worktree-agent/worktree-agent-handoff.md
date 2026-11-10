# Handoff: worktree-agent (HAC-38, P6.1 — CTO amendment AM-2)

## Current state
- Branch `daypart/hac-fhdic-build` @ 5a79ef1 (P6.1 boundary, QGR `…iteration-complete-20261110-1533-fe84520.md`, UX evidence beside it), pushed. Base dbe19da (P5.2 land).
- P6.1 delivered: D1 member app `/` + research console `/admin` (one source `static/index.html`, markers rendered by `demo/surfaces.py`); D2 demo tags removed, production copy, seeded fictional persona (`demo/persona.py`, `persona_v1.json`, `tools/make_persona.py`), "Start a fresh journal"; D3 `GET /api/journals/{id}/timeline` (`passport/timeline.py`, newest 60 saves).
- Decisions: addendum G31–G34; A&D amended (SC1, §4.10, T1.2, API + component tables, Human input).
- Checks at the boundary: engine 2939 passed (sealed incl.), repo-root 352 passed / 3 skipped, pyright 0, browser suite 26/26 (local chromium via /tmp/chrdeps libs), persona --check ok.

## Next action
- After CI green on 5a79ef1: hand `ready @ 5a79ef1` to the CTO (reassign HAC-38).
- P6.2 waits on HAC-68 (visual spec rev 3, due 2026-11-13): apply rev 3 to both surfaces, "clone updated" moment, timeline view, admin pipeline diagram, browser suite on /admin. Deferred to P6.2: C5 (timeline step change between entries), U2 (registry `allowed_use` "demo display" text, sealed-pinned).

## Principal Decisions Needed
- None.
